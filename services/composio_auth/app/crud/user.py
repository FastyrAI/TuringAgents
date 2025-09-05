"""
User CRUD operations.
Handles all database operations related to users.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.user import User
from schemas.user import UserCreate, UserUpdate
from core.security import get_password_hash, verify_password


class UserCRUD:
    """CRUD operations for User model."""

    def create(self, db: Session, user_create: UserCreate) -> User:
        """
        Create a new user.

        Args:
            db: Database session
            user_create: User creation data

        Returns:
            User: The created user object

        Raises:
            ValueError: If email or username already exists
        """
        # Check if email already exists
        if self.get_by_email(db, email=user_create.email):
            raise ValueError("Email already registered")

        # Check if username already exists
        if self.get_by_username(db, username=user_create.username):
            raise ValueError("Username already taken")

        # Hash the password
        hashed_password = get_password_hash(user_create.password)

        # Create user object
        db_user = User(
            name=user_create.name,
            email=user_create.email,
            username=user_create.username,
            hashed_password=hashed_password,
        )

        # Add to database
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        return db_user

    def get(self, db: Session, user_id: int) -> Optional[User]:
        """
        Get user by ID.

        Args:
            db: Database session
            user_id: User ID to retrieve

        Returns:
            Optional[User]: User object if found, None otherwise
        """
        return db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """
        Get user by email address.

        Args:
            db: Database session
            email: Email address to search for

        Returns:
            Optional[User]: User object if found, None otherwise
        """
        return db.query(User).filter(User.email == email).first()

    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            db: Database session
            username: Username to search for

        Returns:
            Optional[User]: User object if found, None otherwise
        """
        return db.query(User).filter(User.username == username).first()

    def get_multi(
        self, db: Session, skip: int = 0, limit: int = 100, active_only: bool = True
    ) -> List[User]:
        """
        Get multiple users with pagination.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: If True, return only active users

        Returns:
            List[User]: List of user objects
        """
        query = db.query(User)

        if active_only:
            query = query.filter(User.is_active == True)

        return query.offset(skip).limit(limit).all()

    def update(
        self, db: Session, user_id: int, user_update: UserUpdate
    ) -> Optional[User]:
        """
        Update user information.

        Args:
            db: Database session
            user_id: ID of user to update
            user_update: Update data

        Returns:
            Optional[User]: Updated user object if found, None otherwise
        """
        db_user = self.get(db, user_id=user_id)
        if not db_user:
            return None

        # Update fields if provided
        update_data = user_update.dict(exclude_unset=True)

        # Check for email uniqueness if updating email
        if "email" in update_data and update_data["email"] != db_user.email:
            if self.get_by_email(db, email=update_data["email"]):
                raise ValueError("Email already registered")

        # Check for username uniqueness if updating username
        if "username" in update_data and update_data["username"] != db_user.username:
            if self.get_by_username(db, username=update_data["username"]):
                raise ValueError("Username already taken")

        # Apply updates
        for field, value in update_data.items():
            setattr(db_user, field, value)

        db.commit()
        db.refresh(db_user)

        return db_user

    def delete(self, db: Session, user_id: int) -> bool:
        """
        Delete a user (soft delete by setting is_active to False).

        Args:
            db: Database session
            user_id: ID of user to delete

        Returns:
            bool: True if user was deleted, False if not found
        """
        db_user = self.get(db, user_id=user_id)
        if not db_user:
            return False

        # Soft delete - set is_active to False
        db_user.is_active = False
        db.commit()

        return True

    def hard_delete(self, db: Session, user_id: int) -> bool:
        """
        Permanently delete a user from the database.

        Args:
            db: Database session
            user_id: ID of user to delete

        Returns:
            bool: True if user was deleted, False if not found
        """
        db_user = self.get(db, user_id=user_id)
        if not db_user:
            return False

        db.delete(db_user)
        db.commit()

        return True

    def authenticate(self, db: Session, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user with email and password.

        Args:
            db: Database session
            email: User's email address
            password: Plain text password

        Returns:
            Optional[User]: User object if authentication successful, None otherwise
        """
        user = self.get_by_email(db, email=email)
        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        return user

    def change_password(
        self, db: Session, user_id: int, current_password: str, new_password: str
    ) -> bool:
        """
        Change user password.

        Args:
            db: Database session
            user_id: ID of user
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            bool: True if password was changed, False otherwise
        """
        user = self.get(db, user_id=user_id)
        if not user:
            return False

        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            return False

        # Hash and set new password
        user.hashed_password = get_password_hash(new_password)
        db.commit()

        return True

    def count(self, db: Session, active_only: bool = True) -> int:
        """
        Count total number of users.

        Args:
            db: Database session
            active_only: If True, count only active users

        Returns:
            int: Total number of users
        """
        query = db.query(User)

        if active_only:
            query = query.filter(User.is_active == True)

        return query.count()


# Create global instance
user_crud = UserCRUD()
