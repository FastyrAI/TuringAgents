"""
Composio service for handling external tool integrations.
Handles OAuth flows, tool discovery, and tool execution using the actual Composio API.
Requires users to have their own OpenAI API keys configured.

Note: OAuth URLs in fallback scenarios use placeholder URLs. In production, these should be
configured to use the actual Composio OAuth endpoints or your custom OAuth flow.
"""

import os
import logging
from typing import List, Optional
from composio_client.types.connected_account_create_params import (
    ConnectionStateUnionMember3,
)
from sqlalchemy.orm import Session
from core.exceptions import (
    ConfigurationError,
    ValidationError,
    ExternalServiceError,
    InternalServerError,
    ToolExecutionError,
)
from services.user_key_utils import (
    get_user_openai_key_safe,
    update_user_key_usage,
    get_user_key_info,
)
from clients.composio_client import composio_client
from models.composio_connection import ComposioConnection
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class ComposioConnectionService:
    def __init__(
        self, session: Session, user_id: str, provider: str, api_key: str = None
    ):
        self.client = composio_client.client
        self.user_id = user_id
        self.provider = provider
        self.api_key = api_key
        self.db_session = session

    def get_provider_config(self):
        # Use the ComposioClient wrapper to get auth configs
        from clients.composio_client import composio_client
        auth_configs = composio_client.composio_auth_configs()
        auth_config = auth_configs.get(self.provider)
        auth_config_id = auth_config["id"]
        auth_type = auth_config.get("auth_type")
        return auth_config_id, auth_type

    def get_auth_url(self):
        auth_config_id, auth_type = self.get_provider_config()
        response = self.client.connected_accounts.initiate(
            user_id=self.user_id,
            auth_config_id=auth_config_id,
            callback_url="http://0.0.0.0:8000/",
        )
        return response

    def connect_with_api_key(self):
        auth_config_id, auth_type = self.get_provider_config()
        response = self.client.connected_accounts.initiate(
            user_id=self.user_id,
            auth_config_id=auth_config_id,
            config=ConnectionStateUnionMember3(
                auth_scheme="API_KEY", val={"status": "ACTIVE", "api_key": self.api_key}
            ),
        )
        return response

    def save_to_db(self, response):
        # Convert user_id to int if it's a string
        user_id_int = (
            int(self.user_id) if isinstance(self.user_id, str) else self.user_id
        )

        connection_record = ComposioConnection(
            user_id=user_id_int,
            composio_connected_account_id=response.id,
            provider=self.provider,
        )

        self.db_session.add(connection_record)
        self.db_session.commit()
        return connection_record


def remove_examples(tool_details):
    if isinstance(tool_details, dict):
        return {
            key: remove_examples(value)
            for key, value in tool_details.items()
            if key != "examples"
        }
    elif isinstance(tool_details, list):
        return [remove_examples(item) for item in tool_details]
    else:
        return tool_details


def get_openai_client_for_user(user_id: int, db_session: Optional[Session] = None):
    """
    Get OpenAI client using user's API key (required).

    Args:
        user_id: User ID
        db_session: Database session for fetching user's API key

    Returns:
        Tuple[OpenAI_client, str, bool]: (client, key_type, is_user_key)
        - client: Configured OpenAI client
        - key_type: Always "user"
        - is_user_key: Always True

    Raises:
        ConfigurationError: If user doesn't have an API key configured
    """
    from openai import OpenAI

    # Try to get user's API key first
    user_api_key = None
    if db_session:
        try:
            user_api_key = get_user_openai_key_safe(user_id, db_session)
        except Exception as e:
            logger.debug(f"Could not get user {user_id}'s API key: {e}")

    # Require user to have their own API key - no fallback to global key
    if user_api_key:
        logger.info(f"Using user {user_id}'s OpenAI API key for Composio operations")
        client = OpenAI(api_key=user_api_key, timeout=30.0)
        return client, "user", True
    else:
        # No fallback - user must have their own API key
        raise ConfigurationError(
            f"User {user_id} must add their own OpenAI API key to use this feature. Please add your API key in your profile settings."
        )


def get_relevant_toolkits_for_prompt(
    prompt: str,
    available_toolkits: List[str],
    openai_client,
    user_id: int = None,
    db_session: Optional[Session] = None,
) -> List[str]:
    """
    Intelligently select relevant toolkits based on user  prompt and available toolkits.
    Uses a lightweight OpenAI call to determine which toolkits are needed.
    """
    try:
        # Create a focused prompt for toolkit selection
        toolkit_selection_prompt = f"""
        Based on this user request, which of these available toolkits are relevant?
        
        User request: {prompt}
        
        Available toolkits: {', '.join(available_toolkits)}
        
        Respond with ONLY the toolkit names separated by commas. No explanations.
        Example: gmail,googlecalendar
        
        If the request is unclear, return the most commonly used toolkits.
        """

        # Use a smaller, cheaper model for toolkit selection
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",  # Cheaper and faster than gpt-4
            messages=[{"role": "user", "content": toolkit_selection_prompt}],
            max_tokens=50,  # Very short response
            temperature=0.1,  # Low randomness for consistent results
            timeout=10,
        )

        selected_toolkits = [
            tk.strip()
            for tk in response.choices[0].message.content.split(",")
            if tk.strip()
            in available_toolkits  # Ensure only available toolkits are selected
        ]

        # Fallback: if no toolkits selected or error, return first 2 available
        if not selected_toolkits:
            logger.warning("No toolkits selected by AI, using fallback")
            selected_toolkits = (
                available_toolkits[:2]
                if len(available_toolkits) >= 2
                else available_toolkits
            )

        # Limit to maximum 3 toolkits to keep token usage low
        if len(selected_toolkits) > 3:
            selected_toolkits = selected_toolkits[:3]
            logger.info(
                f"Limited toolkits to 3 to reduce token usage: {selected_toolkits}"
            )

        # Update usage tracking if user key was used
        if user_id and db_session:
            try:
                # Check if user has their own key by trying to get key info
                key_info = get_user_key_info(user_id, db_session)
                if key_info.get("has_key") and key_info.get("is_active"):
                    update_user_key_usage(user_id, db_session)
                    logger.debug(f"Updated last_used_at for user {user_id}'s API key")
            except Exception as e:
                logger.debug(f"Could not update usage for user {user_id}: {e}")

        return selected_toolkits

    except Exception as e:
        logger.error(f"Error in toolkit selection: {e}, using fallback")
        # Fallback: return first 2 available toolkits
        return (
            available_toolkits[:2]
            if len(available_toolkits) >= 2
            else available_toolkits
        )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def perform_action(user_id: str, prompt: str, db_session: Optional[Session] = None):
    """Execute action with robust error handling and retries."""

    # Input validation
    if not user_id or not user_id.strip():
        raise ValidationError("User ID cannot be empty")

    if not prompt or len(prompt.strip()) < 3:
        raise ValidationError("Prompt must be at least 3 characters")

    if len(prompt) > 2000:
        raise ValidationError("Prompt too long (max 2000 characters)")

    # Environment validation
    composio_key = os.getenv("COMPOSIO_API_KEY")

    if not composio_key:
        raise ConfigurationError("Composio API key not configured")

    # Convert user_id to int for database operations
    user_id_int = int(user_id) if isinstance(user_id, str) else user_id

    try:
        # Initialize clients with timeout
        from openai import OpenAI
        from composio import Composio
        from composio_openai import OpenAIProvider

        # Get user-specific OpenAI client (required)
        openai_client, key_type, is_user_key = get_openai_client_for_user(
            user_id_int, db_session
        )
        logger.info(f"Using {key_type} OpenAI key for user {user_id}")

        provider = OpenAIProvider()
        composio_client_instance = Composio(api_key=composio_key, provider=provider)

        # Get tools with timeout - Smart filtering approach
        try:
            auth_configs = composio_client_instance.auth_configs.list()
            available_toolkits = [item.toolkit.slug for item in auth_configs.items]

            # Stage 1: Use lightweight model to determine relevant toolkits from available ones
            relevant_toolkits = get_relevant_toolkits_for_prompt(
                prompt, available_toolkits, openai_client, user_id_int, db_session
            )

            # Stage 2: Get tools only for relevant toolkits with reduced limit
            tools = composio_client_instance.tools.get(
                user_id=user_id,
                toolkits=relevant_toolkits,
                limit=100,
            )
            tools = remove_examples(tools)
            logger.info(
                f"Selected {len(relevant_toolkits)} toolkits from {len(available_toolkits)} available: {relevant_toolkits}"
            )

        except Exception as e:
            logger.error(f"Failed to get Composio tools: {e}")
            raise ExternalServiceError("Failed to connect to Composio service")

        # OpenAI request with timeout
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4",
                tools=tools,
                messages=[{"role": "user", "content": prompt}],
                timeout=30,
            )
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise ExternalServiceError("AI service temporarily unavailable")

        # Handle tool calls
        try:
            result = composio_client_instance.provider.handle_tool_calls(
                response=response, user_id=user_id
            )
            if not result:
                return {"error": "No result returned from action"}

            # Update usage tracking for successful operations with user's API key
            if is_user_key and db_session:
                try:
                    update_user_key_usage(user_id_int, db_session)
                    logger.debug(
                        f"Updated last_used_at for user {user_id}'s API key after successful action"
                    )
                except Exception as e:
                    logger.debug(
                        f"Could not update usage for user {user_id} after action: {e}"
                    )

            # Process result safely
            if result and result[0].get("data"):
                data = result[0]["data"]
                return data.get("items", data)
            elif not result[0].get("successful"):
                return {"error": result[0].get("error")}

            return {"error": "No result returned from given action"}

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            if "No connected account found" in str(e):
                return {"error": "Please Connect the relevant account."}
            raise ToolExecutionError("Failed to execute the requested action")

    except (
        ConfigurationError,
        ValidationError,
        ExternalServiceError,
        ToolExecutionError,
    ):
        raise
    except Exception as e:
        logger.error(f"Unexpected error in perform_action: {e}")
        raise InternalServerError("Action execution failed")
