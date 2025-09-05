"""
User-related Pydantic schemas.
Defines the structure for user data validation in requests and responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """Base user schema with common fields."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Full name of the user"
    )
    email: EmailStr = Field(..., description="User's email address")
    username: str = Field(
        ..., min_length=3, max_length=50, description="Unique username"
    )


class UserCreate(UserBase):
    """Schema for user creation (registration)."""

    password: str = Field(
        ..., min_length=8, max_length=128, description="User's password"
    )


class UserUpdate(BaseModel):
    """Schema for user updates (partial updates allowed)."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="Full name of the user"
    )
    email: Optional[EmailStr] = Field(None, description="User's email address")
    username: Optional[str] = Field(
        None, min_length=3, max_length=50, description="Unique username"
    )
    is_active: Optional[bool] = Field(
        None, description="Whether the user account is active"
    )


class UserInDB(UserBase):
    """Schema for user data as stored in database."""

    id: int = Field(..., description="Unique user identifier")
    hashed_password: str = Field(..., description="Hashed password")
    created_at: datetime = Field(..., description="User creation timestamp")
    is_active: bool = Field(..., description="Whether the user account is active")

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    """Schema for user data in API responses."""

    id: int = Field(..., description="Unique user identifier")
    created_at: datetime = Field(..., description="User creation timestamp")
    is_active: bool = Field(..., description="Whether the user account is active")

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Schema for list of users in API responses."""

    users: list[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of users per page")
