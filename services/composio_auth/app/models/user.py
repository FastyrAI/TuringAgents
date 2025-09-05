"""
User database model.
Defines the User table structure and relationships.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class User(Base):
    """
    User model representing the users table.

    Fields:
        id: Primary key, auto-incrementing integer
        name: Full name of the user
        email: Unique email address (indexed)
        username: Unique username (indexed)
        hashed_password: Bcrypt hashed password
        created_at: Timestamp when user was created
        is_active: Whether the user account is active
    """

    __tablename__ = "users"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # User information
    name = Column(String(100), nullable=False, comment="Full name of the user")
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User's email address",
    )
    username = Column(
        String(50), unique=True, nullable=False, index=True, comment="Unique username"
    )

    # Security
    hashed_password = Column(
        String(255), nullable=False, comment="Bcrypt hashed password"
    )

    # Metadata
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="User creation timestamp",
    )
    is_active = Column(
        Boolean, default=True, comment="Whether the user account is active"
    )

    # Relationships
    composio_connections = relationship("ComposioConnection", back_populates="user")
    openai_key = relationship("OpenAIKey", back_populates="user", uselist=False)

    # Indexes for better query performance
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_username", "username"),
        Index("idx_users_created_at", "created_at"),
    )

    def __repr__(self):
        """String representation of the User model."""
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated (always True for existing users)."""
        return True

    @property
    def is_anonymous(self) -> bool:
        """Check if user is anonymous (always False for existing users)."""
        return False
