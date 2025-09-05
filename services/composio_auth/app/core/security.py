"""
Security utilities for authentication and authorization.
Handles JWT token creation/validation, password hashing, and session management.
"""

import secrets
import hashlib
import time
import base64
from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Set
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TOKEN_BLACKLIST: Set[str] = set()

FAILED_ATTEMPTS: Dict[str, Dict[str, Union[int, float]]] = {}

ACTIVE_SESSIONS: Dict[str, Dict[str, Union[str, float]]] = {}

# Constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5 minutes
SESSION_CLEANUP_INTERVAL = 3600  # 1 hour


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.

    Args:
        plain_password: The plain text password to verify
        hashed_password: The hashed password to check against

    Returns:
        bool: True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: The plain text password to hash

    Returns:
        str: The hashed password
    """
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    session_id: Optional[str] = None,
) -> str:
    """
    Create a JWT access token with enhanced security.

    Args:
        data: The data to encode in the token (usually user_id)
        expires_delta: Optional custom expiration time
        session_id: Optional session ID for session tracking

    Returns:
        str: The encoded JWT token
    """
    to_encode = data.copy()

    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    # Add security claims
    now = datetime.utcnow()
    jti = secrets.token_urlsafe(32)  # Unique token ID

    to_encode.update(
        {
            "exp": expire,
            "iat": now,  # Issued at
            "nbf": now,  # Not before
            "jti": jti,  # JWT ID for blacklisting
            "aud": settings.app_name,  # Audience
            "iss": settings.app_name,  # Issuer
        }
    )

    # Add session ID if provided
    if session_id:
        to_encode["sid"] = session_id

        # Track active session
        ACTIVE_SESSIONS[session_id] = {
            "user_id": str(data.get("sub", "")),
            "created_at": time.time(),
            "last_activity": time.time(),
            "jti": jti,
        }

    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )

    logger.info(f"Created JWT token with JTI: {jti}")
    return encoded_jwt


def verify_token(token: str, check_blacklist: bool = True) -> Optional[dict]:
    """
    Verify and decode a JWT token with enhanced security checks.

    Args:
        token: The JWT token to verify
        check_blacklist: Whether to check token blacklist

    Returns:
        Optional[dict]: The decoded token payload if valid, None otherwise
    """
    try:
        # Decode token without verification first to get JTI
        unverified_payload = jwt.get_unverified_claims(token)

        # Check if token is blacklisted
        if check_blacklist and unverified_payload.get("jti") in TOKEN_BLACKLIST:
            logger.warning(
                f"Attempted use of blacklisted token: {unverified_payload.get('jti')}"
            )
            return None

        # Verify token with all security checks
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.app_name,
            issuer=settings.app_name,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
                "require_exp": True,
                "require_iat": True,
                "require_nbf": True,
            },
        )

        # Update session activity if session ID present
        session_id = payload.get("sid")
        if session_id and session_id in ACTIVE_SESSIONS:
            ACTIVE_SESSIONS[session_id]["last_activity"] = time.time()

        return payload

    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        return None


def get_current_user_id(token: str) -> Optional[int]:
    """
    Extract user ID from a JWT token.

    Args:
        token: The JWT token

    Returns:
        Optional[int]: The user ID if token is valid, None otherwise
    """
    payload = verify_token(token)
    if payload is None:
        return None

    user_id: int = payload.get("sub")
    if user_id is None:
        return None

    return user_id


def create_user_token(user_id: int, create_session: bool = True) -> str:
    """
    Create a JWT token for a specific user with session tracking.

    Args:
        user_id: The ID of the user
        create_session: Whether to create a session for tracking

    Returns:
        str: The JWT token
    """
    session_id = create_session_id() if create_session else None
    return create_access_token(data={"sub": str(user_id)}, session_id=session_id)


def extract_token_from_header(authorization: str) -> Optional[str]:
    """
    Extract JWT token from Authorization header.

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")

    Returns:
        Optional[str]: The extracted token if valid format, None otherwise
    """
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]


def validate_token_format(token: str) -> bool:
    """
    Basic validation of JWT token format.

    Args:
        token: The JWT token to validate

    Returns:
        bool: True if token format is valid, False otherwise
    """
    if not token:
        return False

    # JWT tokens have 3 parts separated by dots
    parts = token.split(".")
    if len(parts) != 3:
        return False

    # Each part should be base64 encoded
    try:
        import base64

        for part in parts:
            base64.b64decode(part + "=" * (-len(part) % 4))
        return True
    except Exception:
        return False


# Password validation utilities
def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength with enhanced security checks.

    Args:
        password: The password to validate

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if len(password) > 128:
        return False, "Password must be less than 128 characters long"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"

    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character"

    # Check for common weak passwords
    weak_passwords = [
        "password",
        "123456",
        "password123",
        "admin",
        "qwerty",
        "letmein",
        "welcome",
        "monkey",
        "dragon",
        "password1",
    ]
    if password.lower() in weak_passwords:
        return False, "Password is too common. Please choose a stronger password"

    # Check for sequential or repetitive patterns
    if has_sequential_chars(password) or has_repetitive_chars(password):
        return False, "Password should not contain sequential or repetitive patterns"

    return True, "Password is strong"


def has_sequential_chars(password: str, min_length: int = 3) -> bool:
    """Check if password contains sequential characters."""
    for i in range(len(password) - min_length + 1):
        sequence = password[i : i + min_length]
        if all(
            ord(sequence[j]) == ord(sequence[j - 1]) + 1
            for j in range(1, len(sequence))
        ) or all(
            ord(sequence[j]) == ord(sequence[j - 1]) - 1
            for j in range(1, len(sequence))
        ):
            return True
    return False


def has_repetitive_chars(password: str, min_length: int = 3) -> bool:
    """Check if password contains repetitive characters."""
    for i in range(len(password) - min_length + 1):
        if len(set(password[i : i + min_length])) == 1:
            return True
    return False


# Session and security management
def create_session_id() -> str:
    """Create a secure session ID."""
    return secrets.token_urlsafe(32)


def blacklist_token(token: str) -> bool:
    """
    Add a token to the blacklist.

    Args:
        token: JWT token to blacklist

    Returns:
        bool: True if token was blacklisted, False if invalid token
    """
    try:
        payload = jwt.get_unverified_claims(token)
        jti = payload.get("jti")

        if jti:
            TOKEN_BLACKLIST.add(jti)
            logger.info(f"Blacklisted token with JTI: {jti}")

            # Also invalidate session if present
            session_id = payload.get("sid")
            if session_id and session_id in ACTIVE_SESSIONS:
                del ACTIVE_SESSIONS[session_id]
                logger.info(f"Invalidated session: {session_id}")

            return True

        return False

    except Exception as e:
        logger.error(f"Failed to blacklist token: {str(e)}")
        return False


def invalidate_user_sessions(user_id: str):
    """
    Invalidate all active sessions for a user.

    Args:
        user_id: User ID whose sessions to invalidate
    """
    sessions_to_remove = []

    for session_id, session_data in ACTIVE_SESSIONS.items():
        if session_data.get("user_id") == str(user_id):
            # Add JTI to blacklist
            jti = session_data.get("jti")
            if jti:
                TOKEN_BLACKLIST.add(jti)

            sessions_to_remove.append(session_id)

    # Remove sessions
    for session_id in sessions_to_remove:
        del ACTIVE_SESSIONS[session_id]

    logger.info(f"Invalidated {len(sessions_to_remove)} sessions for user {user_id}")


def track_failed_login(identifier: str) -> bool:
    """
    Track failed login attempt and check if account should be locked.

    Args:
        identifier: Email or username to track

    Returns:
        bool: True if account should be locked, False otherwise
    """
    now = time.time()

    if identifier not in FAILED_ATTEMPTS:
        FAILED_ATTEMPTS[identifier] = {"count": 0, "first_attempt": now}

    attempt_data = FAILED_ATTEMPTS[identifier]

    # Reset counter if lockout period has passed
    if now - attempt_data["first_attempt"] > LOCKOUT_DURATION:
        attempt_data["count"] = 0
        attempt_data["first_attempt"] = now

    attempt_data["count"] += 1

    logger.warning(f"Failed login attempt #{attempt_data['count']} for {identifier}")

    return attempt_data["count"] >= MAX_FAILED_ATTEMPTS


def is_account_locked(identifier: str) -> tuple[bool, int]:
    """
    Check if account is locked due to failed attempts.

    Args:
        identifier: Email or username to check

    Returns:
        tuple[bool, int]: (is_locked, seconds_remaining)
    """
    if identifier not in FAILED_ATTEMPTS:
        return False, 0

    attempt_data = FAILED_ATTEMPTS[identifier]

    if attempt_data["count"] < MAX_FAILED_ATTEMPTS:
        return False, 0

    now = time.time()
    time_since_first = now - attempt_data["first_attempt"]

    if time_since_first >= LOCKOUT_DURATION:
        # Lockout period expired, reset
        del FAILED_ATTEMPTS[identifier]
        return False, 0

    remaining = int(LOCKOUT_DURATION - time_since_first)
    return True, remaining


def clear_failed_attempts(identifier: str):
    """Clear failed login attempts for an identifier."""
    if identifier in FAILED_ATTEMPTS:
        del FAILED_ATTEMPTS[identifier]
        logger.info(f"Cleared failed attempts for {identifier}")


def cleanup_expired_sessions():
    """Clean up expired sessions and tokens."""
    now = time.time()
    session_timeout = 24 * 3600  # 24 hours

    expired_sessions = []
    expired_jtis = set()

    for session_id, session_data in ACTIVE_SESSIONS.items():
        last_activity = session_data.get("last_activity", 0)

        if now - last_activity > session_timeout:
            expired_sessions.append(session_id)
            jti = session_data.get("jti")
            if jti:
                expired_jtis.add(jti)

    # Remove expired sessions
    for session_id in expired_sessions:
        del ACTIVE_SESSIONS[session_id]

    # Add JTIs to blacklist
    TOKEN_BLACKLIST.update(expired_jtis)

    if expired_sessions:
        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")


def get_active_session_count(user_id: str) -> int:
    """Get number of active sessions for a user."""
    count = 0
    for session_data in ACTIVE_SESSIONS.values():
        if session_data.get("user_id") == str(user_id):
            count += 1
    return count


def get_security_headers() -> Dict[str, str]:
    """Get security headers for HTTP responses."""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    }


def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(token: str, expected_token: str) -> bool:
    """Verify CSRF token using constant-time comparison."""
    return secrets.compare_digest(token, expected_token)


def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for logging/storage."""
    return hashlib.sha256(data.encode()).hexdigest()[:16]


# ===== API Key Encryption Utilities =====


def _get_encryption_key() -> bytes:
    """
    Get or generate encryption key for API key encryption.

    Returns:
        bytes: Encryption key for Fernet
    """
    # Use the encryption key from settings
    key_string = settings.encryption_key.encode()

    # Use PBKDF2 to derive a proper 32-byte key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"openai_key_salt",  # Static salt for consistency
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(key_string))
    return key


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an OpenAI API key for secure storage.

    Args:
        api_key: Plain text OpenAI API key

    Returns:
        str: Encrypted API key as base64 string

    Raises:
        ValueError: If API key is empty or invalid
        Exception: If encryption fails
    """
    if not api_key or not api_key.strip():
        raise ValueError("API key cannot be empty")

    try:
        # Get encryption key
        key = _get_encryption_key()
        fernet = Fernet(key)

        # Encrypt the API key
        encrypted_key = fernet.encrypt(api_key.encode())

        # Return as base64 string for database storage
        return base64.urlsafe_b64encode(encrypted_key).decode()

    except Exception as e:
        logger.error(f"Failed to encrypt API key: {str(e)}")
        raise Exception("Failed to encrypt API key")


def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypt an OpenAI API key from secure storage.

    Args:
        encrypted_api_key: Encrypted API key as base64 string

    Returns:
        str: Plain text OpenAI API key

    Raises:
        ValueError: If encrypted key is empty or invalid
        Exception: If decryption fails
    """
    if not encrypted_api_key or not encrypted_api_key.strip():
        raise ValueError("Encrypted API key cannot be empty")

    try:
        # Get encryption key
        key = _get_encryption_key()
        fernet = Fernet(key)

        # Decode from base64 and decrypt
        encrypted_data = base64.urlsafe_b64decode(encrypted_api_key.encode())
        decrypted_key = fernet.decrypt(encrypted_data)

        return decrypted_key.decode()

    except Exception as e:
        logger.error(f"Failed to decrypt API key: {str(e)}")
        raise Exception("Failed to decrypt API key")


def validate_api_key_format(api_key: str) -> bool:
    """
    Basic validation of OpenAI API key format.

    Args:
        api_key: API key to validate

    Returns:
        bool: True if format appears valid, False otherwise
    """
    if not api_key or not isinstance(api_key, str):
        return False

    # OpenAI API keys typically start with 'sk-' and are 51 characters long
    # But format may change, so we'll be lenient
    if api_key.startswith("sk-") and len(api_key.strip()) >= 40:
        return True

    return False
