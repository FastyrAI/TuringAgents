"""
OpenAI API key related Pydantic schemas.
Defines the structure for OpenAI API key data validation in requests and responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator, ConfigDict


class OpenAIKeyCreate(BaseModel):
    """Schema for creating a new OpenAI API key."""

    api_key: str = Field(
        ...,
        min_length=40,
        max_length=200,
        description="OpenAI API key (format: sk-...)",
    )

    @validator("api_key")
    def validate_api_key_format(cls, v):
        """Validate OpenAI API key format."""
        if not v.startswith("sk-"):
            raise ValueError('OpenAI API key must start with "sk-"')
        if len(v.strip()) < 40:
            raise ValueError("OpenAI API key appears to be too short")
        return v.strip()


class OpenAIKeyUpdate(BaseModel):
    """Schema for updating an OpenAI API key."""

    api_key: Optional[str] = Field(
        None,
        min_length=40,
        max_length=200,
        description="New OpenAI API key (format: sk-...)",
    )
    is_active: Optional[bool] = Field(None, description="Whether the API key is active")

    @validator("api_key")
    def validate_api_key_format(cls, v):
        """Validate OpenAI API key format if provided."""
        if v is not None:
            if not v.startswith("sk-"):
                raise ValueError('OpenAI API key must start with "sk-"')
            if len(v.strip()) < 40:
                raise ValueError("OpenAI API key appears to be too short")
            return v.strip()
        return v


class OpenAIKeyResponse(BaseModel):
    """Schema for OpenAI API key in API responses (without exposing the actual key)."""

    id: int = Field(..., description="Unique API key identifier")
    user_id: int = Field(..., description="User ID who owns the key")
    is_active: bool = Field(..., description="Whether the API key is active")
    created_at: datetime = Field(..., description="Key creation timestamp")
    updated_at: datetime = Field(..., description="Key update timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last time key was used")
    key_preview: str = Field(
        ..., description="Masked preview of the API key (e.g., sk-...****)"
    )

    model_config = ConfigDict(from_attributes=True)


class OpenAIKeyWithDecrypted(OpenAIKeyResponse):
    """Schema for internal use when the actual API key is needed."""

    decrypted_api_key: str = Field(..., description="Decrypted OpenAI API key")


class OpenAIKeyStatusResponse(BaseModel):
    """Schema for API key status operations."""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[OpenAIKeyResponse] = Field(
        None, description="API key data if successful"
    )


class OpenAIKeyValidationResponse(BaseModel):
    """Schema for API key validation response."""

    valid: bool = Field(..., description="Whether the API key is valid")
    message: str = Field(..., description="Validation result message")
    model_info: Optional[dict] = Field(
        None, description="Available models if key is valid"
    )


class OpenAIKeyErrorResponse(BaseModel):
    """Schema for API key related errors."""

    success: bool = Field(default=False, description="Always false for errors")
    error: str = Field(..., description="Error type identifier")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(None, description="Additional error details")
