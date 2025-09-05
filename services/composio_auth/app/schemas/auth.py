"""
Authentication-related Pydantic schemas.
Defines the structure for authentication data validation.
"""

from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class LoginRequest(BaseModel):
    """Schema for user login request."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=1, description="User's password")


class RegisterRequest(BaseModel):
    """Schema for user registration request."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Full name of the user"
    )
    email: EmailStr = Field(..., description="User's email address")
    username: str = Field(
        ..., min_length=3, max_length=50, description="Unique username"
    )
    password: str = Field(
        ..., min_length=8, max_length=128, description="User's password"
    )


class TokenResponse(BaseModel):
    """Schema for authentication token response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Type of token")
    expires_in: int = Field(..., description="Token expiration time in minutes")


class AuthResponse(BaseModel):
    """Schema for authentication response."""

    success: bool = Field(..., description="Whether the authentication was successful")
    message: str = Field(..., description="Response message")
    data: Optional[TokenResponse] = Field(
        None, description="Authentication data if successful"
    )


class PasswordChangeRequest(BaseModel):
    """Schema for password change request."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""

    email: EmailStr = Field(..., description="User's email address")


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )
