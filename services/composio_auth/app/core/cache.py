"""
Smart Redis Cache Implementation with Proactive Refresh.

This module provides a Redis-based caching system that automatically refreshes
cached data in the background before it expires, ensuring users never experience
cache misses or API delays.

Key Features:
- Automatic TTL-based expiration
- Proactive background refresh when cache is about to expire
- Graceful fallback when Redis is unavailable
- Connection health monitoring
- Type-safe JSON serialization
"""

import redis
import json
import asyncio
import logging
from typing import Optional, Any, Tuple, Callable
from functools import wraps

from core.config import settings

logger = logging.getLogger(__name__)


class SmartRedisCache:
    """
    Redis cache with smart proactive refresh capabilities.

    Features:
    - Automatic background refresh before expiration
    - Graceful fallback when Redis is unavailable
    - Connection health monitoring
    - Configurable TTL and refresh thresholds
    """

    def __init__(self):
        """Initialize Redis connection with error handling."""
        self.redis_client = None
        self._connect()

    def _connect(self):
        """Establish Redis connection with comprehensive error handling."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=True,
                socket_timeout=settings.redis_socket_timeout,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                retry_on_timeout=True,
                retry_on_error=[ConnectionError, TimeoutError],
                health_check_interval=30,
            )

            # Test connection with ping
            self.redis_client.ping()
            logger.info(f"Redis connection established: {self._get_redis_info()}")

        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            logger.info("Application will continue with direct API calls (no caching)")
            self.redis_client = None

    def _get_redis_info(self) -> str:
        """Get Redis connection info for logging (without sensitive data)."""
        try:
            if not self.redis_client:
                return "Not connected"

            # Parse URL to hide password
            url_parts = settings.redis_url.replace("redis://", "").split("@")
            if len(url_parts) > 1:
                # URL has password - show only host part
                host_part = url_parts[-1]
                return f"redis://{host_part} (DB: {settings.redis_db})"
            else:
                # No password in URL
                return f"{settings.redis_url} (DB: {settings.redis_db})"

        except Exception:
            return "Unknown"

    def is_connected(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            bool: True if Redis is available and responsive
        """
        if not self.redis_client:
            return False

        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.debug(f"Redis health check failed: {e}")
            return False

    def get_with_ttl(self, key: str) -> Tuple[Optional[Any], int]:
        """
        Get cached value and its remaining TTL.

        Args:
            key: Cache key

        Returns:
            Tuple[Optional[Any], int]: (cached_data, remaining_ttl_seconds)
            - cached_data: Deserialized data or None if not found
            - remaining_ttl_seconds: Time until expiration (0 if expired/not found)
        """
        if not self.is_connected():
            return None, 0

        try:
            # Use pipeline for atomic operation
            pipe = self.redis_client.pipeline()
            pipe.get(key)
            pipe.ttl(key)

            data, ttl = pipe.execute()

            # Parse JSON data if available
            parsed_data = None
            if data:
                try:
                    parsed_data = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON for key {key}: {e}")
                    # Delete corrupted data
                    self.redis_client.delete(key)
                    return None, 0

            # Return TTL (Redis returns -1 for keys without expiration, -2 for non-existent keys)
            remaining_ttl = max(0, ttl) if ttl >= 0 else 0

            return parsed_data, remaining_ttl

        except Exception as e:
            logger.warning(f"Redis GET failed for key '{key}': {e}")
            return None, 0

    def set(self, key: str, value: Any, ttl: int) -> bool:
        """
        Set cached value with TTL.

        Args:
            key: Cache key
            value: Data to cache (will be JSON serialized)
            ttl: Time to live in seconds

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            # Serialize data to JSON
            data = json.dumps(value, default=str, ensure_ascii=False)

            # Set with expiration
            result = self.redis_client.setex(key, ttl, data)

            if result:
                logger.debug(f"Cached data for key '{key}' (TTL: {ttl}s)")

            return bool(result)

        except Exception as e:
            logger.warning(f"Redis SET failed for key '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete cached value.

        Args:
            key: Cache key to delete

        Returns:
            bool: True if key was deleted, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            result = self.redis_client.delete(key)
            logger.debug(f"Deleted cache key '{key}'")
            return bool(result)
        except Exception as e:
            logger.warning(f"Redis DELETE failed for key '{key}': {e}")
            return False

    def smart_get(
        self,
        key: str,
        fetch_func: Callable[[], Any],
        ttl: Optional[int] = None,
        refresh_threshold: Optional[int] = None,
    ) -> Optional[Any]:
        """
        Smart cache retrieval with proactive refresh.

        This is the core method that implements the smart refresh logic:
        1. Cache miss → Fetch fresh data immediately
        2. Cache hit with plenty of time → Return cached data
        3. Cache hit but expiring soon → Return cached data + refresh in background

        Args:
            key: Cache key
            fetch_func: Function to fetch fresh data (should be callable without args)
            ttl: Cache TTL in seconds (default: settings.composio_cache_ttl)
            refresh_threshold: Refresh when TTL below this (default: settings.cache_refresh_threshold)

        Returns:
            Optional[Any]: Cached or fresh data, None if all methods fail
        """
        # Use configured defaults
        ttl = ttl or settings.composio_cache_ttl
        refresh_threshold = refresh_threshold or settings.cache_refresh_threshold

        # Add namespace prefix to key
        namespaced_key = f"{settings.cache_key_prefix}-{key}"

        # Get current cache and TTL
        cached_data, current_ttl = self.get_with_ttl(namespaced_key)

        # Case 1: Cache miss - fetch immediately
        if cached_data is None:
            logger.info(f"Cache miss for '{key}', fetching fresh data")
            try:
                fresh_data = fetch_func()

                # Cache the fresh data
                if self.set(namespaced_key, fresh_data, ttl):
                    logger.info(f"Fetched and cached fresh data for '{key}'")
                else:
                    logger.warning(f"Fetched data for '{key}' but failed to cache")

                return fresh_data

            except Exception as e:
                logger.error(f"Failed to fetch fresh data for '{key}': {e}")
                return None

        # Case 2: Cache hit, but expiring soon - return cache + refresh in background
        if 0 < current_ttl < refresh_threshold:
            logger.info(
                f"Cache for '{key}' expiring in {current_ttl}s, triggering background refresh"
            )

            # Start background refresh task (fire and forget)
            asyncio.create_task(
                self._background_refresh(namespaced_key, key, fetch_func, ttl)
            )

        # Case 3: Cache hit with plenty of time - just return cached data
        logger.debug(f"Cache hit for '{key}' (TTL: {current_ttl}s)")
        return cached_data

    async def _background_refresh(
        self,
        namespaced_key: str,
        original_key: str,
        fetch_func: Callable[[], Any],
        ttl: int,
    ):
        """
        Background task to refresh cache without blocking the main request.

        Args:
            namespaced_key: Full Redis key with namespace
            original_key: Original key (for logging)
            fetch_func: Function to fetch fresh data
            ttl: TTL for the refreshed data
        """
        try:
            logger.info(f"Background refresh starting for '{original_key}'")

            # Fetch fresh data
            fresh_data = fetch_func()

            # Update cache with fresh data
            if self.set(namespaced_key, fresh_data, ttl):
                logger.info(f"Background refresh completed for '{original_key}'")
            else:
                logger.warning(
                    f"Background refresh fetched data but failed to cache for '{original_key}'"
                )

        except Exception as e:
            logger.error(f"Background refresh failed for '{original_key}': {e}")

    def get_cache_stats(self, key: str) -> dict:
        """
        Get cache statistics for debugging.

        Args:
            key: Cache key to inspect

        Returns:
            dict: Cache statistics
        """
        namespaced_key = f"{settings.cache_key_prefix}{key}"
        data, ttl = self.get_with_ttl(namespaced_key)

        return {
            "key": key,
            "namespaced_key": namespaced_key,
            "exists": data is not None,
            "ttl_seconds": ttl,
            "ttl_human": (
                f"{ttl // 3600}h {(ttl % 3600) // 60}m {ttl % 60}s"
                if ttl > 0
                else "expired"
            ),
            "data_size_bytes": len(json.dumps(data)) if data else 0,
            "redis_connected": self.is_connected(),
            "refresh_threshold": settings.cache_refresh_threshold,
            "will_refresh_soon": (
                0 < ttl < settings.cache_refresh_threshold if ttl > 0 else False
            ),
        }


# Global cache instance
cache = SmartRedisCache()


def cached(
    key: str, ttl: Optional[int] = None, refresh_threshold: Optional[int] = None
):
    """
    Decorator for automatic function result caching with smart refresh.

    Args:
        key: Cache key
        ttl: Cache TTL in seconds
        refresh_threshold: Refresh threshold in seconds

    Usage:
        @cached("my_expensive_function", ttl=3600)
        def expensive_computation():
            # This will be cached for 1 hour
            return complex_calculation()
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a function that calls the original with args/kwargs
            def fetch_func():
                return func(*args, **kwargs)

            return cache.smart_get(key, fetch_func, ttl, refresh_threshold)

        return wrapper

    return decorator
