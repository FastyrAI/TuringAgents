"""
Service factory for creating user-aware service instances.
Provides a centralized way to create services with proper user context.
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from services.openai_service import OpenAIService
from services.user_key_utils import (
    get_openai_service_config,
    UserKeyError,
    get_user_key_info,
    validate_user_can_use_openai,
)
from models.user import User

logger = logging.getLogger(__name__)


class ServiceFactory:
    """Factory for creating user-aware service instances."""

    def __init__(self, user: User, db_session: Session):
        """
        Initialize the service factory for a specific user.

        Args:
            user: User object
            db_session: Database session
        """
        self.user = user
        self.db_session = db_session
        self.user_id = user.id

    def create_openai_service(self, require_user_key: bool = False) -> OpenAIService:
        """
        Create an OpenAI service instance for the user.

        Args:
            require_user_key: If True, raises error if user doesn't have API key

        Returns:
            OpenAI service configured for the user

        Raises:
            UserKeyError: If require_user_key=True and user doesn't have valid key
        """
        if require_user_key:
            validate_user_can_use_openai(self.user, self.db_session)

        config = get_openai_service_config(self.user_id, self.db_session)

        if config["use_user_key"]:
            logger.info(f"Creating OpenAI service with user {self.user_id}'s API key")
            return OpenAIService.create_with_user(self.user_id, self.db_session)
        else:
            if require_user_key:
                raise UserKeyError(
                    f"User API key required but not available: {config['error']}"
                )

            logger.info(
                f"Creating OpenAI service with global API key for user {self.user_id}"
            )
            return OpenAIService.create_global()

    def get_service_capabilities(self) -> Dict[str, Any]:
        """
        Get information about what services are available for this user.

        Returns:
            Dict with service capabilities
        """
        openai_config = get_openai_service_config(self.user_id, self.db_session)
        user_key_info = get_user_key_info(self.user_id, self.db_session)

        return {
            "user_id": self.user_id,
            "user_active": self.user.is_active,
            "openai": {
                "available": openai_config["use_user_key"]
                or openai_config["fallback_to_global"],
                "using_user_key": openai_config["use_user_key"],
                "can_fallback_to_global": openai_config["fallback_to_global"],
                "key_status": openai_config["key_status"],
                "error": openai_config.get("error"),
                "key_info": user_key_info,
            },
        }

    def validate_user_access(self, service_name: str) -> Dict[str, Any]:
        """
        Validate user access to a specific service.

        Args:
            service_name: Name of the service to validate

        Returns:
            Dict with validation results
        """
        result = {
            "service": service_name,
            "user_id": self.user_id,
            "can_access": False,
            "reason": None,
            "suggestions": [],
        }

        if not self.user.is_active:
            result["reason"] = "User account is inactive"
            result["suggestions"].append("Contact support to activate your account")
            return result

        if service_name.lower() == "openai":
            config = get_openai_service_config(self.user_id, self.db_session)

            if config["use_user_key"]:
                result["can_access"] = True
                result["reason"] = "User has valid OpenAI API key"
            elif config["fallback_to_global"]:
                result["can_access"] = True
                result["reason"] = "Using global OpenAI API key (limited features)"
                result["suggestions"].append(
                    "Add your own OpenAI API key for full access"
                )
            else:
                result["reason"] = config.get("error", "No OpenAI access available")
                result["suggestions"].extend(
                    [
                        "Add an OpenAI API key in your account settings",
                        "Ensure your API key is active and valid",
                    ]
                )

        return result


def create_user_service_factory(user: User, db_session: Session) -> ServiceFactory:
    """
    Create a service factory for a user.

    Args:
        user: User object
        db_session: Database session

    Returns:
        ServiceFactory instance for the user
    """
    return ServiceFactory(user, db_session)


def get_user_openai_service(
    user: User, db_session: Session, require_user_key: bool = False
) -> OpenAIService:
    """
    Convenience function to get OpenAI service for a user.

    Args:
        user: User object
        db_session: Database session
        require_user_key: If True, requires user to have their own API key

    Returns:
        OpenAI service configured for the user
    """
    factory = create_user_service_factory(user, db_session)
    return factory.create_openai_service(require_user_key=require_user_key)


def validate_user_service_access(
    user: User, db_session: Session, service_name: str
) -> Dict[str, Any]:
    """
    Convenience function to validate user's access to a service.

    Args:
        user: User object
        db_session: Database session
        service_name: Service to validate

    Returns:
        Validation results
    """
    factory = create_user_service_factory(user, db_session)
    return factory.validate_user_access(service_name)
