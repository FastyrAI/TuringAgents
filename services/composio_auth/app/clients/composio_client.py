import os
import logging
from composio import Composio
from core.cache import cache

logger = logging.getLogger(__name__)


class ComposioClient:

    def __init__(self):
        self.__composio_key = os.getenv("COMPOSIO_API_KEY")
        self.client = Composio(api_key=self.__composio_key)

    def get_active_auth_configs(self):
        """
        Get active authentication configurations from Composio API.
        
        Returns:
            dict: Dictionary mapping provider slugs to their auth config data
            
        Raises:
            Exception: If no auth configs are found
        """
        auth_configs = self.client.auth_configs.list()
        if auth_configs:
            result = {}
            for data in auth_configs.items:
                auth_type = data.auth_scheme.lower()
                logger.info(
                    f"Provider '{data.toolkit.slug}': normalized to '{auth_type}'"
                )
                result[data.toolkit.slug] = {"id": data.id, "auth_type": auth_type}
            return result
        raise Exception("No auth configs found")

    def fetch_fresh_composio_configs(self):
        """
        Fetch fresh auth configs from Composio API.
        This function is called by the smart cache when data needs to be refreshed.
        """
        try:
            configs = self.get_active_auth_configs()  # returns dict
            logger.info(f"Fetched {len(configs)} fresh configs from Composio API")
            return configs
        except Exception as e:
            logger.error(f"Failed to fetch configs from Composio API: {e}")
            raise  # Re-raise so smart cache can handle fallback

    def composio_auth_configs(self):
        """
        Get Composio auth configs with smart Redis caching.

        Features:
        - Automatic 24-hour TTL with proactive 1-hour refresh
        - Background refresh to prevent API delays
        - Graceful fallback when Redis is unavailable
        - Comprehensive error handling

        Returns:
            dict: Auth configs from Composio API or empty dict on failure
        """
        cache_key = "auth_configs"

        # Use smart cache with automatic refresh
        result = cache.smart_get(
            key=cache_key,
            fetch_func=self.fetch_fresh_composio_configs,
            ttl=None,
            refresh_threshold=None,
        )

        # Fallback to empty dict if everything fails
        return result or {}

    def get_composio_providers(self):
        """Fetch provider list from cached configs or return fallback list."""
        configs = self.composio_auth_configs()
        if configs:
            return list(configs.keys())
        return ["gmail", "googlecalendar"]

    def get_provider_auth_type(self, provider: str):
        """
        Get the authentication type for a given provider.
        Returns 'oauth2', 'api_key', or 'oauth2' (fallback)
        """
        auth_config = self.composio_auth_configs().get(provider)
        # Extract auth type from the new data structure
        auth_type = (
            auth_config.get("auth_type") if isinstance(auth_config, dict) else "oauth2"
        )
        return auth_type


composio_client = ComposioClient()
