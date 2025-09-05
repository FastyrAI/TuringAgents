"""
Core configuration settings for the FastAPI application.
Handles environment variables, database settings, JWT configuration, Redis caching, and CORS.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    # Todo: Load these values from .env file
    # Application Configuration
    app_name: str = Field(default="FastAPI Authentication Demo", env="APP_NAME")
    debug: bool = Field(default=True, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")

    # JWT Configuration
    jwt_secret_key: str = Field(
        default="your-super-secret-jwt-key-here", env="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=480, env="ACCESS_TOKEN_EXPIRE_MINUTES"  # 8 hours
    )

    # CORS Configuration
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="ALLOWED_ORIGINS",
    )

    # Security Configuration
    bcrypt_rounds: int = Field(default=12, env="BCRYPT_ROUNDS")

    # Composio Configuration
    composio_api_key: str = Field(default="", env="COMPOSIO_API_KEY")

    # OpenAI Configuration
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")

    # Encryption Configuration
    encryption_key: str = Field(
        default="your-super-secret-encryption-key-here-must-be-32-bytes-long",
        env="ENCRYPTION_KEY",
    )

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_socket_timeout: int = Field(default=5, env="REDIS_SOCKET_TIMEOUT")
    redis_socket_connect_timeout: int = Field(
        default=5, env="REDIS_SOCKET_CONNECT_TIMEOUT"
    )

    # Cache Configuration
    composio_cache_ttl: int = Field(
        default=86400, env="COMPOSIO_CACHE_TTL"  # 24 hours in seconds
    )
    cache_refresh_threshold: int = Field(
        default=3600, env="CACHE_REFRESH_THRESHOLD"  # 1 hour in seconds
    )
    cache_key_prefix: str = Field(default="composio_demo:", env="CACHE_KEY_PREFIX")

    database_url: str = os.getenv("DATABASE_URL", "")


    class Config:
        env_file = "../../.env"  # Look for .env in parent directory
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


# Create global settings instance
settings = Settings()


# Validate critical settings
def validate_settings():
    """Validate that critical settings are properly configured."""
    if settings.jwt_secret_key == "your-super-secret-jwt-key-here":
        raise ValueError("JWT_SECRET_KEY must be set to a secure value in production")

    if (
        settings.encryption_key
        == "your-super-secret-encryption-key-here-must-be-32-bytes-long"
    ):
        raise ValueError("ENCRYPTION_KEY must be set to a secure value in production")


# Validate settings on import (only in production)
if settings.environment == "production":
    validate_settings()
