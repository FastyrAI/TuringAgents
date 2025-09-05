"""
OpenAI service for natural language processing.
Converts user queries into structured tool calls.
Now supports user-specific API keys from the database.
"""

from typing import Dict, Any, Tuple, Optional
import logging
from openai import OpenAI
from sqlalchemy.orm import Session
from core.config import settings
from crud.openai_key import openai_key_crud

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI API with support for user-specific keys."""

    def __init__(
        self, user_id: Optional[int] = None, db_session: Optional[Session] = None
    ):
        """
        Initialize the OpenAI service.

        Args:
            user_id: Optional user ID to use user-specific API key
            db_session: Optional database session for user key retrieval
        """
        self.user_id = user_id
        self.db_session = db_session
        self.global_api_key = settings.openai_api_key
        self.client = None
        self._user_api_key = None

        # Initialize client with appropriate API key
        self._initialize_client()

    def _initialize_client(self):
        """Initialize OpenAI client with the best available API key."""
        api_key = self._get_best_api_key()

        if api_key:
            try:
                # Only use the new client-based approach, don't set global api_key
                self.client = OpenAI(api_key=api_key)
                logger.debug(
                    f"OpenAI client initialized with {'user' if self._user_api_key else 'global'} API key"
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {str(e)}")
                self.client = None
        else:
            logger.warning("No OpenAI API key available - running in fallback mode")
            self.client = None

    def _get_best_api_key(self) -> Optional[str]:
        """
        Get the best available API key (user-specific first, then global).

        Returns:
            Optional[str]: API key to use, None if no key available
        """
        # Try to get user-specific API key first
        if self.user_id and self.db_session:
            try:
                user_key = openai_key_crud.get_decrypted_api_key(
                    self.db_session, self.user_id
                )
                if user_key:
                    self._user_api_key = user_key
                    return user_key
            except Exception as e:
                logger.warning(
                    f"Failed to get user API key for user {self.user_id}: {str(e)}"
                )

        # Fallback to global API key
        if self.global_api_key:
            return self.global_api_key

        return None

    def _update_last_used(self):
        """Update the last_used_at timestamp for user's API key if applicable."""
        if self._user_api_key and self.user_id and self.db_session:
            try:
                openai_key_crud.update_last_used(self.db_session, self.user_id)
            except Exception as e:
                logger.warning(
                    f"Failed to update last_used for user {self.user_id}: {str(e)}"
                )

    def set_user_context(self, user_id: int, db_session: Session):
        """
        Set user context and reinitialize client with user's API key.

        Args:
            user_id: User ID
            db_session: Database session
        """
        self.user_id = user_id
        self.db_session = db_session
        self._user_api_key = None
        self._initialize_client()

    def clear_user_context(self):
        """Clear user context and use global API key."""
        self.user_id = None
        self.db_session = None
        self._user_api_key = None
        self._initialize_client()

    def hostile_message_check(self, content: str) -> Tuple[bool, str]:
        """
        Check if the content contains hostile or inappropriate material.
        Uses user-specific API key if available, falls back to global key.

        Args:
            content: The text content to check

        Returns:
            Tuple of (is_flagged, hostilities_description)
        """
        if not self.client:
            # If no API key available, skip moderation check
            logger.warning("No OpenAI API key available for content moderation")
            return False, ""

        try:
            response = self.client.moderations.create(
                model="omni-moderation-latest", input=content
            ).results[0]

            hostilities = []

            if response.flagged == True:
                for category, value in response.categories.to_dict().items():
                    if value:
                        if "/" in category:
                            category = (
                                category.split("/")[0]
                                + "("
                                + category.split("/")[1]
                                + ")"
                            )
                        hostilities.append(category)

            # Update last_used timestamp if using user's API key
            if self._user_api_key:
                self._update_last_used()
                logger.info(
                    f"Content moderation completed using user {self.user_id}'s API key"
                )
            else:
                logger.info("Content moderation completed using global API key")

            return response.flagged, " and ".join(hostilities)

        except Exception as e:
            # If moderation check fails, allow the content to proceed
            # but log the error for monitoring
            logger.error(f"Content moderation check failed: {e}")
            return False, ""

    def get_api_key_info(self) -> Dict[str, Any]:
        """
        Get information about the currently active API key.

        Returns:
            Dict with API key information
        """
        return {
            "has_user_key": bool(self._user_api_key),
            "has_global_key": bool(self.global_api_key),
            "has_client": bool(self.client),
            "user_id": self.user_id,
            "using_key_type": (
                "user"
                if self._user_api_key
                else "global" if self.global_api_key else "none"
            ),
        }

    async def process_natural_language(self, query: str) -> Dict[str, Any]:
        """
        Process natural language query and extract tool information.
        Uses user-specific API key if available, falls back to global key.

        Args:
            query: Natural language query from user

        Returns:
            Structured tool information with parameters
        """
        if not self.client:
            # Fallback to mock processing if no API key
            logger.warning(
                "No OpenAI API key available for natural language processing"
            )
            return self._mock_process_query(query)

        try:
            # Use OpenAI to process the query with the new client API
            import asyncio

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a helpful assistant that converts natural language requests into structured tool calls.
                            
                            Available tools:
                            - gmail_send_email: Send emails via Gmail
                            - google_calendar_create_event: Create calendar events
                            
                            For each request, extract:
                            1. The appropriate tool ID
                            2. Relevant parameters (to, subject, body for emails; title, description, date for events)
                            
                            Return a JSON object with 'tool' and 'params' fields.""",
                        },
                        {"role": "user", "content": query},
                    ],
                    max_tokens=200,
                    temperature=0.1,
                ),
            )

            # Extract the response content
            content = response.choices[0].message.content

            # Update last_used timestamp if using user's API key
            if self._user_api_key:
                self._update_last_used()
                logger.info(
                    f"Natural language processing completed using user {self.user_id}'s API key"
                )
            else:
                logger.info(
                    "Natural language processing completed using global API key"
                )

            # Try to parse the response as JSON
            try:
                import json

                result = json.loads(content)

                # Validate the response structure
                if "tool" in result and "params" in result:
                    return result
                else:
                    raise ValueError("Invalid response structure")

            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, fall back to keyword matching
                logger.warning(
                    "Failed to parse OpenAI response as JSON, falling back to keyword matching"
                )
                return self._fallback_process_query(query)

        except Exception as e:
            # If OpenAI fails, fall back to keyword matching
            logger.error(f"OpenAI natural language processing failed: {str(e)}")
            return self._fallback_process_query(query)

    def _fallback_process_query(self, query: str) -> Dict[str, Any]:
        """Fallback processing using keyword matching."""
        query_lower = query.lower()

        if "email" in query_lower or "send" in query_lower:
            return {
                "tool": "gmail_send_email",
                "params": {
                    "to": self._extract_email(query),
                    "subject": self._extract_subject(query),
                    "body": query,
                },
            }
        elif (
            "calendar" in query_lower
            or "event" in query_lower
            or "meeting" in query_lower
        ):
            return {
                "tool": "google_calendar_create_event",
                "params": {
                    "title": self._extract_title(query),
                    "description": query,
                    "date": self._extract_date(query),
                },
            }
        else:
            return {
                "tool": "unknown",
                "params": {},
                "error": "Could not determine tool from query",
            }

    def _mock_process_query(self, query: str) -> Dict[str, Any]:
        """Mock processing for development/testing."""
        return self._fallback_process_query(query)

    def _extract_email(self, query: str) -> str:
        """Extract email address from query (basic implementation)."""
        import re

        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, query)
        return emails[0] if emails else "user@example.com"

    def _extract_subject(self, query: str) -> str:
        """Extract subject from query (basic implementation)."""
        # Look for common subject indicators
        if "about" in query.lower():
            parts = query.lower().split("about")
            if len(parts) > 1:
                return parts[1].strip().capitalize()
        return "Email from natural language query"

    def _extract_title(self, query: str) -> str:
        """Extract event title from query (basic implementation)."""
        # Look for common title indicators
        if "meeting" in query.lower():
            return "Meeting"
        elif "event" in query.lower():
            return "Event"
        return "Event from natural language query"

    def _extract_date(self, query: str) -> str:
        """Extract date from query (basic implementation)."""
        query_lower = query.lower()
        if "tomorrow" in query_lower:
            return "tomorrow"
        elif "today" in query_lower:
            return "today"
        elif "next week" in query_lower:
            return "next week"
        return "tomorrow"

    @classmethod
    def create_with_user(cls, user_id: int, db_session: Session) -> "OpenAIService":
        """
        Create an OpenAI service instance with user context.

        Args:
            user_id: User ID
            db_session: Database session

        Returns:
            OpenAIService instance configured for the user
        """
        return cls(user_id=user_id, db_session=db_session)

    @classmethod
    def create_global(cls) -> "OpenAIService":
        """
        Create an OpenAI service instance using global API key.

        Returns:
            OpenAIService instance configured with global key
        """
        return cls()


# Convenience functions for easy service creation
def get_openai_service_for_user(user_id: int, db_session: Session) -> OpenAIService:
    """
    Get an OpenAI service instance for a specific user.

    Args:
        user_id: User ID
        db_session: Database session

    Returns:
        OpenAI service configured with user's API key
    """
    return OpenAIService.create_with_user(user_id, db_session)


def get_global_openai_service() -> OpenAIService:
    """
    Get an OpenAI service instance using global configuration.

    Returns:
        OpenAI service configured with global API key
    """
    return OpenAIService.create_global()
