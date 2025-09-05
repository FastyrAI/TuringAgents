"""
Input validation and sanitization utilities.
Provides comprehensive validation for all user inputs to prevent injection attacks and ensure data integrity.
"""

import re
import html
import urllib.parse
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

# Constants for validation
MAX_PROMPT_LENGTH = 2000
MIN_PROMPT_LENGTH = 3
MAX_EMAIL_LENGTH = 254
MAX_USERNAME_LENGTH = 50
MIN_USERNAME_LENGTH = 3
MAX_NAME_LENGTH = 100
MIN_NAME_LENGTH = 1

# Dangerous patterns for SQL injection, command injection, etc.
DANGEROUS_PATTERNS = [
    # SQL injection patterns
    r"('|\\'|;|\||\*|%|<|>|\{|\})",
    r"(union\s+select)|(insert\s+into)|(delete\s+from)|(update\s+set)|(drop\s+table)",
    r"(exec\s*\()|(sp_)|(xp_)",
    # Command injection patterns
    r"(\||\&|\;|\$|\`)",
    r"(\.\./)|(\.\.\\)|(/etc/)|(\%2e\%2e)",
    # Script injection patterns
    r"(<script)|(javascript:)|(vbscript:)|(onload\s*=)|(onerror\s*=)",
    r"(<iframe)|(eval\s*\()|(document\.)|(window\.)",
    # Path traversal
    r"(\.\./)|(\.\.\\)|(\%2e\%2e\%2f)|(\%2e\%2e\%5c)",
]

# Compile patterns for better performance
COMPILED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in DANGEROUS_PATTERNS
]


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


class InputSanitizer:
    """Utility class for input sanitization."""

    @staticmethod
    def sanitize_html(text: str) -> str:
        """Sanitize HTML content to prevent XSS attacks."""
        if not isinstance(text, str):
            return str(text)
        return html.escape(text)

    @staticmethod
    def sanitize_sql(text: str) -> str:
        """Basic SQL injection prevention through escaping."""
        if not isinstance(text, str):
            return str(text)

        # Escape single quotes
        text = text.replace("'", "''")
        # Remove null bytes
        text = text.replace("\x00", "")
        return text

    @staticmethod
    def sanitize_url(url: str) -> str:
        """Sanitize URL to prevent injection."""
        if not isinstance(url, str):
            return str(url)
        return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=")

    @staticmethod
    def remove_control_characters(text: str) -> str:
        """Remove control characters that might cause issues."""
        if not isinstance(text, str):
            return str(text)

        # Remove control characters except for common whitespace
        return "".join(char for char in text if ord(char) >= 32 or char in "\t\n\r")


class InputValidator:
    """Comprehensive input validation."""

    @staticmethod
    def is_safe_text(text: str, allow_html: bool = False) -> Tuple[bool, str]:
        """
        Check if text contains potentially dangerous patterns.

        Args:
            text: Text to validate
            allow_html: Whether to allow HTML content

        Returns:
            Tuple of (is_safe, error_message)
        """
        if not isinstance(text, str):
            return False, "Input must be a string"

        # Check for dangerous patterns
        for pattern in COMPILED_PATTERNS:
            if pattern.search(text):
                logger.warning(
                    f"Dangerous pattern detected in input: {pattern.pattern}"
                )
                return False, "Input contains potentially dangerous content"

        # Additional HTML checks if not allowed
        if not allow_html:
            html_patterns = [r"<[^>]*>", r"&[a-zA-Z]+;"]
            for pattern in html_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return False, "HTML content not allowed"

        return True, ""

    @staticmethod
    def validate_prompt(prompt: str) -> str:
        """
        Validate and sanitize AI prompt input.

        Args:
            prompt: User prompt to validate

        Returns:
            Sanitized prompt

        Raises:
            ValidationError: If prompt is invalid
        """
        if not prompt or not isinstance(prompt, str):
            raise ValidationError("Prompt cannot be empty")

        # Remove control characters
        prompt = InputSanitizer.remove_control_characters(prompt)

        # Check length
        if len(prompt.strip()) < MIN_PROMPT_LENGTH:
            raise ValidationError(
                f"Prompt must be at least {MIN_PROMPT_LENGTH} characters"
            )

        if len(prompt) > MAX_PROMPT_LENGTH:
            raise ValidationError(
                f"Prompt too long (max {MAX_PROMPT_LENGTH} characters)"
            )

        # Check for dangerous patterns
        is_safe, error_msg = InputValidator.is_safe_text(prompt, allow_html=False)
        if not is_safe:
            raise ValidationError(f"Invalid prompt: {error_msg}")

        # Additional AI-specific checks
        if prompt.count("\n") > 20:  # Prevent extremely long multi-line inputs
            raise ValidationError("Prompt contains too many line breaks")

        return prompt.strip()

    @staticmethod
    def validate_email(email: str) -> str:
        """
        Validate email format and security.

        Args:
            email: Email to validate

        Returns:
            Sanitized email

        Raises:
            ValidationError: If email is invalid
        """
        if not email or not isinstance(email, str):
            raise ValidationError("Email cannot be empty")

        email = email.strip().lower()

        # Check length
        if len(email) > MAX_EMAIL_LENGTH:
            raise ValidationError(f"Email too long (max {MAX_EMAIL_LENGTH} characters)")

        # Basic email format validation
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise ValidationError("Invalid email format")

        # Check for dangerous patterns
        is_safe, error_msg = InputValidator.is_safe_text(email)
        if not is_safe:
            raise ValidationError(f"Invalid email: {error_msg}")

        return email

    @staticmethod
    def validate_username(username: str) -> str:
        """
        Validate username format and security.

        Args:
            username: Username to validate

        Returns:
            Sanitized username

        Raises:
            ValidationError: If username is invalid
        """
        if not username or not isinstance(username, str):
            raise ValidationError("Username cannot be empty")

        username = username.strip()

        # Check length
        if len(username) < MIN_USERNAME_LENGTH:
            raise ValidationError(
                f"Username must be at least {MIN_USERNAME_LENGTH} characters"
            )

        if len(username) > MAX_USERNAME_LENGTH:
            raise ValidationError(
                f"Username too long (max {MAX_USERNAME_LENGTH} characters)"
            )

        # Username format validation (alphanumeric + underscore, dash)
        username_pattern = r"^[a-zA-Z0-9_-]+$"
        if not re.match(username_pattern, username):
            raise ValidationError(
                "Username can only contain letters, numbers, underscores, and dashes"
            )

        # Check for dangerous patterns
        is_safe, error_msg = InputValidator.is_safe_text(username)
        if not is_safe:
            raise ValidationError(f"Invalid username: {error_msg}")

        return username

    @staticmethod
    def validate_name(name: str) -> str:
        """
        Validate full name format and security.

        Args:
            name: Name to validate

        Returns:
            Sanitized name

        Raises:
            ValidationError: If name is invalid
        """
        if not name or not isinstance(name, str):
            raise ValidationError("Name cannot be empty")

        name = name.strip()

        # Check length
        if len(name) < MIN_NAME_LENGTH:
            raise ValidationError(f"Name must be at least {MIN_NAME_LENGTH} character")

        if len(name) > MAX_NAME_LENGTH:
            raise ValidationError(f"Name too long (max {MAX_NAME_LENGTH} characters)")

        # Name format validation (letters, spaces, common punctuation)
        name_pattern = r"^[a-zA-Z\s\.\'-]+$"
        if not re.match(name_pattern, name):
            raise ValidationError(
                "Name can only contain letters, spaces, periods, apostrophes, and hyphens"
            )

        # Check for dangerous patterns
        is_safe, error_msg = InputValidator.is_safe_text(name)
        if not is_safe:
            raise ValidationError(f"Invalid name: {error_msg}")

        return name

    @staticmethod
    def validate_user_id(user_id: str) -> int:
        """
        Validate user ID format.

        Args:
            user_id: User ID to validate

        Returns:
            Validated user ID as integer

        Raises:
            ValidationError: If user ID is invalid
        """
        if not user_id:
            raise ValidationError("User ID cannot be empty")

        try:
            user_id_int = int(user_id)
            if user_id_int <= 0:
                raise ValidationError("User ID must be positive")
            return user_id_int
        except ValueError:
            raise ValidationError("User ID must be a valid number")

    @staticmethod
    def validate_api_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate API parameters for potential security issues.

        Args:
            params: Parameters to validate

        Returns:
            Sanitized parameters

        Raises:
            ValidationError: If parameters are invalid
        """
        if not isinstance(params, dict):
            raise ValidationError("Parameters must be a dictionary")

        sanitized_params = {}

        for key, value in params.items():
            # Validate key
            if not isinstance(key, str) or not key.strip():
                raise ValidationError("Parameter keys must be non-empty strings")

            # Check key for dangerous patterns
            is_safe, error_msg = InputValidator.is_safe_text(key)
            if not is_safe:
                raise ValidationError(f"Invalid parameter key '{key}': {error_msg}")

            # Validate value
            if isinstance(value, str):
                # Check string values for dangerous patterns
                is_safe, error_msg = InputValidator.is_safe_text(value)
                if not is_safe:
                    raise ValidationError(
                        f"Invalid parameter value for '{key}': {error_msg}"
                    )

                # Sanitize string value
                sanitized_params[key] = InputSanitizer.sanitize_html(value)
            elif isinstance(value, (int, float, bool)):
                sanitized_params[key] = value
            elif isinstance(value, list):
                # Validate list items
                sanitized_list = []
                for item in value:
                    if isinstance(item, str):
                        is_safe, error_msg = InputValidator.is_safe_text(item)
                        if not is_safe:
                            raise ValidationError(
                                f"Invalid list item in '{key}': {error_msg}"
                            )
                        sanitized_list.append(InputSanitizer.sanitize_html(item))
                    else:
                        sanitized_list.append(item)
                sanitized_params[key] = sanitized_list
            else:
                # For other types, convert to string and validate
                str_value = str(value)
                is_safe, error_msg = InputValidator.is_safe_text(str_value)
                if not is_safe:
                    raise ValidationError(
                        f"Invalid parameter value for '{key}': {error_msg}"
                    )
                sanitized_params[key] = str_value

        return sanitized_params


# Pydantic models for request validation
class ValidatedPromptRequest(BaseModel):
    """Validated prompt request model."""

    prompt: str = Field(..., min_length=MIN_PROMPT_LENGTH, max_length=MAX_PROMPT_LENGTH)

    @validator("prompt")
    def validate_prompt_content(cls, v):
        return InputValidator.validate_prompt(v)


class ValidatedUserCreate(BaseModel):
    """Validated user creation model."""

    name: str = Field(..., min_length=MIN_NAME_LENGTH, max_length=MAX_NAME_LENGTH)
    email: str = Field(..., max_length=MAX_EMAIL_LENGTH)
    username: str = Field(
        ..., min_length=MIN_USERNAME_LENGTH, max_length=MAX_USERNAME_LENGTH
    )
    password: str = Field(..., min_length=8, max_length=128)

    @validator("name")
    def validate_name_content(cls, v):
        return InputValidator.validate_name(v)

    @validator("email")
    def validate_email_content(cls, v):
        return InputValidator.validate_email(v)

    @validator("username")
    def validate_username_content(cls, v):
        return InputValidator.validate_username(v)


# Helper functions for FastAPI integration
def validate_and_sanitize_prompt(prompt: str) -> str:
    """FastAPI-friendly prompt validation."""
    try:
        return InputValidator.validate_prompt(prompt)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid prompt: {str(e)}"
        )


def validate_and_sanitize_user_id(user_id: str) -> int:
    """FastAPI-friendly user ID validation."""
    try:
        return InputValidator.validate_user_id(user_id)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid user ID: {str(e)}"
        )
