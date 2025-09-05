"""
User API key utilities for services.
Provides helper functions for services to easily access user-specific API keys.
"""

import logging
from typing import Optional, Tuple, Dict, Any
from functools import wraps
from sqlalchemy.orm import Session

from crud.openai_key import openai_key_crud
from models.user import User
from core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class UserKeyError(Exception):
    """Custom exception for user API key related errors."""

    pass


class UserKeyNotFoundError(UserKeyError):
    """Raised when user doesn't have an API key."""

    pass


class UserKeyInactiveError(UserKeyError):
    """Raised when user's API key is inactive."""

    pass


def get_user_openai_key(user_id: int, db_session: Session) -> str:
    """
    Get user's decrypted OpenAI API key.

    Args:
        user_id: User ID
        db_session: Database session

    Returns:
        str: Decrypted OpenAI API key

    Raises:
        UserKeyNotFoundError: If user doesn't have an API key
        UserKeyInactiveError: If user's API key is inactive
        UserKeyError: If there's an error retrieving the key
    """
    try:
        # Get user's API key record
        user_key_record = openai_key_crud.get_by_user_id(db_session, user_id)

        if not user_key_record:
            raise UserKeyNotFoundError(f"User {user_id} doesn't have an OpenAI API key")

        if not user_key_record.is_active:
            raise UserKeyInactiveError(f"User {user_id}'s OpenAI API key is inactive")

        # Get decrypted key
        decrypted_key = openai_key_crud.get_decrypted_api_key(db_session, user_id)

        if not decrypted_key:
            raise UserKeyError(f"Failed to decrypt API key for user {user_id}")

        return decrypted_key

    except (UserKeyNotFoundError, UserKeyInactiveError):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        logger.error(f"Error retrieving API key for user {user_id}: {str(e)}")
        raise UserKeyError(f"Error retrieving API key: {str(e)}")


def check_user_has_openai_key(
    user_id: int, db_session: Session
) -> Tuple[bool, Optional[str]]:
    """
    Check if user has a valid OpenAI API key.

    Args:
        user_id: User ID
        db_session: Database session

    Returns:
        Tuple[bool, Optional[str]]: (has_key, error_message)
        - has_key: True if user has valid key, False otherwise
        - error_message: None if has key, error message if not
    """
    try:
        get_user_openai_key(user_id, db_session)
        return True, None
    except UserKeyNotFoundError:
        return False, "You need to add an OpenAI API key to use this feature"
    except UserKeyInactiveError:
        return (
            False,
            "Your OpenAI API key is inactive. Please activate it or add a new one",
        )
    except UserKeyError as e:
        return False, f"Error with your OpenAI API key: {str(e)}"


def get_user_openai_key_safe(
    user_id: int, db_session: Session, fallback_key: Optional[str] = None
) -> Optional[str]:
    """
    Safely get user's OpenAI API key with fallback.

    Args:
        user_id: User ID
        db_session: Database session
        fallback_key: Optional fallback key to use if user doesn't have one

    Returns:
        Optional[str]: User's API key, fallback key, or None
    """
    try:
        return get_user_openai_key(user_id, db_session)
    except UserKeyError:
        logger.debug(f"User {user_id} doesn't have valid API key, using fallback")
        return fallback_key


def update_user_key_usage(user_id: int, db_session: Session) -> bool:
    """
    Update the last_used_at timestamp for user's API key.

    Args:
        user_id: User ID
        db_session: Database session

    Returns:
        bool: True if updated successfully, False otherwise
    """
    try:
        return openai_key_crud.update_last_used(db_session, user_id)
    except Exception as e:
        logger.warning(f"Failed to update last_used for user {user_id}: {str(e)}")
        return False


def get_user_key_info(user_id: int, db_session: Session) -> Dict[str, Any]:
    """
    Get information about user's API key status.

    Args:
        user_id: User ID
        db_session: Database session

    Returns:
        Dict with key information
    """
    try:
        key_record = openai_key_crud.get_by_user_id(db_session, user_id)

        if not key_record:
            return {
                "has_key": False,
                "is_active": False,
                "error": "No API key found",
                "created_at": None,
                "last_used_at": None,
            }

        return {
            "has_key": True,
            "is_active": key_record.is_active,
            "error": None if key_record.is_active else "API key is inactive",
            "created_at": (
                key_record.created_at.isoformat() if key_record.created_at else None
            ),
            "last_used_at": (
                key_record.last_used_at.isoformat() if key_record.last_used_at else None
            ),
            "updated_at": (
                key_record.updated_at.isoformat() if key_record.updated_at else None
            ),
        }

    except Exception as e:
        logger.error(f"Error getting key info for user {user_id}: {str(e)}")
        return {
            "has_key": False,
            "is_active": False,
            "error": f"Error retrieving key info: {str(e)}",
            "created_at": None,
            "last_used_at": None,
        }


# Decorator for functions that require user API keys
def require_user_openai_key(error_message: str = "OpenAI API key required"):
    """
    Decorator that ensures user has a valid OpenAI API key before calling the function.

    Args:
        error_message: Custom error message to show if key is missing

    Usage:
        @require_user_openai_key("You need an API key to use this feature")
        def my_service_function(user_id: int, db_session: Session, ...):
            # Function will only be called if user has valid API key
            pass
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Try to find user_id and db_session in arguments
            user_id = None
            db_session = None

            # Check args first
            for arg in args:
                if isinstance(arg, int) and user_id is None:
                    user_id = arg
                elif isinstance(arg, Session) and db_session is None:
                    db_session = arg

            # Check kwargs
            if user_id is None:
                user_id = kwargs.get("user_id")
            if db_session is None:
                db_session = kwargs.get("db_session") or kwargs.get("db")

            if user_id is None or db_session is None:
                raise ValueError("Function must have user_id and db_session parameters")

            # Check if user has valid API key
            has_key, error = check_user_has_openai_key(user_id, db_session)
            if not has_key:
                raise UserKeyNotFoundError(f"{error_message}: {error}")

            return func(*args, **kwargs)

        return wrapper

    return decorator


# Context manager for services that use user API keys
class UserOpenAIKeyContext:
    """
    Context manager for working with user OpenAI API keys.

    Usage:
        with UserOpenAIKeyContext(user_id, db_session) as api_key:
            # Use api_key for OpenAI operations
            # last_used_at will be automatically updated on exit
    """

    def __init__(
        self, user_id: int, db_session: Session, auto_update_usage: bool = True
    ):
        """
        Initialize the context manager.

        Args:
            user_id: User ID
            db_session: Database session
            auto_update_usage: Whether to automatically update last_used_at on exit
        """
        self.user_id = user_id
        self.db_session = db_session
        self.auto_update_usage = auto_update_usage
        self.api_key = None

    def __enter__(self) -> str:
        """
        Enter the context and return the user's API key.

        Returns:
            str: User's OpenAI API key

        Raises:
            UserKeyError: If user doesn't have a valid API key
        """
        self.api_key = get_user_openai_key(self.user_id, self.db_session)
        return self.api_key

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context and optionally update usage timestamp.
        """
        if self.auto_update_usage and self.api_key and exc_type is None:
            # Only update usage if no exception occurred
            update_user_key_usage(self.user_id, self.db_session)


# Validation helpers
def validate_user_can_use_openai(user: User, db_session: Session) -> None:
    """
    Validate that a user can use OpenAI features.

    Args:
        user: User object
        db_session: Database session

    Raises:
        UserKeyError: If user cannot use OpenAI features due to API key issues
        ValidationError: If user account is inactive
    """
    if not user.is_active:
        raise ValidationError("User account is inactive")

    has_key, error = check_user_has_openai_key(user.id, db_session)
    if not has_key:
        raise UserKeyError(error)


def get_openai_service_config(user_id: int, db_session: Session) -> Dict[str, Any]:
    """
    Get configuration for OpenAI service based on user's key availability.

    Args:
        user_id: User ID
        db_session: Database session

    Returns:
        Dict with service configuration
    """
    key_info = get_user_key_info(user_id, db_session)

    return {
        "use_user_key": key_info["has_key"] and key_info["is_active"],
        "user_id": user_id if key_info["has_key"] and key_info["is_active"] else None,
        "fallback_to_global": not (key_info["has_key"] and key_info["is_active"]),
        "error": key_info.get("error"),
        "key_status": (
            "active" if key_info["has_key"] and key_info["is_active"] else "inactive"
        ),
    }
