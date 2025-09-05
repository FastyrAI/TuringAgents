"""
OpenAI API key CRUD operations.
Handles all database operations related to OpenAI API keys with encryption support.
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from datetime import datetime

from models.openai_key import OpenAIKey
from schemas.openai_key import OpenAIKeyCreate, OpenAIKeyUpdate, OpenAIKeyResponse
from core.security import encrypt_api_key, decrypt_api_key, validate_api_key_format


class OpenAIKeyCRUD:
    """CRUD operations for OpenAI API key model."""

    def _create_key_preview(self, api_key: str) -> str:
        """
        Create a masked preview of the API key for safe display.

        Args:
            api_key: The full API key

        Returns:
            str: Masked key preview (e.g., sk-...****1234)
        """
        if not api_key or len(api_key) < 10:
            return "sk-...****"

        # Show first 6 characters and last 4 characters
        return f"{api_key[:6]}...****{api_key[-4:]}"

    def _to_response_schema(
        self, db_openai_key: OpenAIKey, decrypted_key: Optional[str] = None
    ) -> OpenAIKeyResponse:
        """
        Convert database model to response schema.

        Args:
            db_openai_key: Database model
            decrypted_key: Decrypted API key for preview generation

        Returns:
            OpenAIKeyResponse: Response schema with key preview
        """
        # Generate key preview
        if decrypted_key:
            key_preview = self._create_key_preview(decrypted_key)
        else:
            # If we don't have decrypted key, create a generic preview
            key_preview = "sk-...****"

        return OpenAIKeyResponse(
            id=db_openai_key.id,
            user_id=db_openai_key.user_id,
            is_active=db_openai_key.is_active,
            created_at=db_openai_key.created_at,
            updated_at=db_openai_key.updated_at,
            last_used_at=db_openai_key.last_used_at,
            key_preview=key_preview,
        )

    def create(
        self, db: Session, user_id: int, openai_key_create: OpenAIKeyCreate
    ) -> OpenAIKey:
        """
        Create a new OpenAI API key for a user.

        Args:
            db: Database session
            user_id: User ID who owns the API key
            openai_key_create: API key creation data

        Returns:
            OpenAIKey: The created API key object

        Raises:
            ValueError: If user already has an API key or key format is invalid
            Exception: If encryption fails
        """
        # Check if user already has an API key (one key per user)
        existing_key = self.get_by_user_id(db, user_id=user_id)
        if existing_key:
            raise ValueError(
                "User already has an OpenAI API key. Use update to modify it."
            )

        # Validate API key format
        if not validate_api_key_format(openai_key_create.api_key):
            raise ValueError("Invalid OpenAI API key format. Expected format: sk-...")

        # Encrypt the API key
        try:
            encrypted_key = encrypt_api_key(openai_key_create.api_key)
        except Exception as e:
            raise Exception(f"Failed to encrypt API key: {str(e)}")

        # Create API key object
        db_openai_key = OpenAIKey(
            user_id=user_id, encrypted_api_key=encrypted_key, is_active=True
        )

        # Add to database
        db.add(db_openai_key)
        db.commit()
        db.refresh(db_openai_key)

        return db_openai_key

    def get(self, db: Session, key_id: int) -> Optional[OpenAIKey]:
        """
        Get OpenAI API key by ID.

        Args:
            db: Database session
            key_id: API key ID to retrieve

        Returns:
            Optional[OpenAIKey]: API key object if found, None otherwise
        """
        return db.query(OpenAIKey).filter(OpenAIKey.id == key_id).first()

    def get_by_user_id(self, db: Session, user_id: int) -> Optional[OpenAIKey]:
        """
        Get OpenAI API key by user ID.

        Args:
            db: Database session
            user_id: User ID to search for

        Returns:
            Optional[OpenAIKey]: API key object if found, None otherwise
        """
        return db.query(OpenAIKey).filter(OpenAIKey.user_id == user_id).first()

    def get_active_by_user_id(self, db: Session, user_id: int) -> Optional[OpenAIKey]:
        """
        Get active OpenAI API key by user ID.

        Args:
            db: Database session
            user_id: User ID to search for

        Returns:
            Optional[OpenAIKey]: Active API key object if found, None otherwise
        """
        return (
            db.query(OpenAIKey)
            .filter(OpenAIKey.user_id == user_id, OpenAIKey.is_active == True)
            .first()
        )

    def update(
        self, db: Session, user_id: int, openai_key_update: OpenAIKeyUpdate
    ) -> Optional[OpenAIKey]:
        """
        Update user's OpenAI API key.

        Args:
            db: Database session
            user_id: User ID whose API key to update
            openai_key_update: Update data

        Returns:
            Optional[OpenAIKey]: Updated API key object if found, None otherwise

        Raises:
            ValueError: If new API key format is invalid
            Exception: If encryption fails
        """
        db_openai_key = self.get_by_user_id(db, user_id=user_id)
        if not db_openai_key:
            return None

        # Update fields if provided
        update_data = openai_key_update.dict(exclude_unset=True)

        # Handle API key update with encryption
        if "api_key" in update_data:
            new_api_key = update_data["api_key"]

            # Validate new API key format
            if not validate_api_key_format(new_api_key):
                raise ValueError(
                    "Invalid OpenAI API key format. Expected format: sk-..."
                )

            # Encrypt the new API key
            try:
                encrypted_key = encrypt_api_key(new_api_key)
                db_openai_key.encrypted_api_key = encrypted_key
            except Exception as e:
                raise Exception(f"Failed to encrypt API key: {str(e)}")

            # Remove from update_data since we handled it manually
            del update_data["api_key"]

        # Apply other updates
        for field, value in update_data.items():
            setattr(db_openai_key, field, value)

        # Update timestamp
        db_openai_key.updated_at = func.now()

        db.commit()
        db.refresh(db_openai_key)

        return db_openai_key

    def delete(self, db: Session, user_id: int) -> bool:
        """
        Delete user's OpenAI API key (hard delete).

        Args:
            db: Database session
            user_id: User ID whose API key to delete

        Returns:
            bool: True if API key was deleted, False if not found
        """
        db_openai_key = self.get_by_user_id(db, user_id=user_id)
        if not db_openai_key:
            return False

        # Hard delete as specified in requirements
        db.delete(db_openai_key)
        db.commit()

        return True

    def get_decrypted_api_key(self, db: Session, user_id: int) -> Optional[str]:
        """
        Get user's decrypted OpenAI API key.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Optional[str]: Decrypted API key if found and active, None otherwise

        Raises:
            Exception: If decryption fails
        """
        db_openai_key = self.get_active_by_user_id(db, user_id=user_id)
        if not db_openai_key:
            return None

        try:
            return decrypt_api_key(db_openai_key.encrypted_api_key)
        except Exception as e:
            raise Exception(f"Failed to decrypt API key: {str(e)}")

    def update_last_used(self, db: Session, user_id: int) -> bool:
        """
        Update the last_used_at timestamp for user's API key.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            bool: True if updated, False if key not found
        """
        db_openai_key = self.get_by_user_id(db, user_id=user_id)
        if not db_openai_key:
            return False

        db_openai_key.last_used_at = func.now()
        db.commit()

        return True

    def toggle_active_status(self, db: Session, user_id: int) -> Optional[OpenAIKey]:
        """
        Toggle the active status of user's API key.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Optional[OpenAIKey]: Updated API key object if found, None otherwise
        """
        db_openai_key = self.get_by_user_id(db, user_id=user_id)
        if not db_openai_key:
            return None

        # Toggle active status
        db_openai_key.is_active = not db_openai_key.is_active
        db_openai_key.updated_at = func.now()

        db.commit()
        db.refresh(db_openai_key)

        return db_openai_key

    def count_active_keys(self, db: Session) -> int:
        """
        Count total number of active API keys.

        Args:
            db: Database session

        Returns:
            int: Total number of active API keys
        """
        return db.query(OpenAIKey).filter(OpenAIKey.is_active == True).count()

    def get_user_key_response(
        self, db: Session, user_id: int
    ) -> Optional[OpenAIKeyResponse]:
        """
        Get user's API key as response schema with key preview.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Optional[OpenAIKeyResponse]: API key response schema if found, None otherwise
        """
        db_openai_key = self.get_by_user_id(db, user_id=user_id)
        if not db_openai_key:
            return None

        # Get decrypted key for preview generation
        try:
            decrypted_key = decrypt_api_key(db_openai_key.encrypted_api_key)
            return self._to_response_schema(db_openai_key, decrypted_key)
        except Exception:
            # If decryption fails, return with generic preview
            return self._to_response_schema(db_openai_key)


# Create global instance
openai_key_crud = OpenAIKeyCRUD()
