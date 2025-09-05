"""
OpenAI API key database model.
Defines the OpenAI API key table structure with encryption support.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class OpenAIKey(Base):
    """
    OpenAI API key model representing the openai_keys table.

    Fields:
        id: Primary key, auto-incrementing integer
        user_id: Foreign key to users table
        encrypted_api_key: Encrypted OpenAI API key
        is_active: Whether the API key is active
        created_at: Timestamp when key was created
        updated_at: Timestamp when key was last updated
        last_used_at: Timestamp when key was last used
    """

    __tablename__ = "openai_keys"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign key to users table
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
        comment="User ID (one key per user)",
    )

    # Encrypted API key
    encrypted_api_key = Column(
        String(500), nullable=False, comment="Encrypted OpenAI API key"
    )

    # Status
    is_active = Column(
        Boolean, default=True, nullable=False, comment="Whether the API key is active"
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Key creation timestamp",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Key update timestamp",
    )
    last_used_at = Column(
        DateTime(timezone=True), nullable=True, comment="Last time key was used"
    )

    # Relationship
    user = relationship("User", back_populates="openai_key")

    # Indexes for better query performance
    __table_args__ = (
        Index("idx_openai_keys_user_id", "user_id"),
        Index("idx_openai_keys_is_active", "is_active"),
        Index("idx_openai_keys_created_at", "created_at"),
    )

    def __repr__(self):
        """String representation of the OpenAI key model."""
        return f"<OpenAIKey(id={self.id}, user_id={self.user_id}, is_active={self.is_active})>"
