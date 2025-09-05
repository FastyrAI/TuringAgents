"""
OpenAI API key validation service.
Tests API keys against OpenAI's API to ensure they are valid and functional.
"""

import asyncio
import logging
from typing import Tuple, Dict, Any, Optional
from openai import OpenAI
from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError

logger = logging.getLogger(__name__)


class OpenAIValidationService:
    """Service for validating OpenAI API keys."""

    def __init__(self):
        """Initialize the validation service."""
        self.timeout = 15.0  # 15 seconds timeout for validation calls

    async def validate_api_key(
        self, api_key: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Validate an OpenAI API key by making a test API call.

        Args:
            api_key: The OpenAI API key to validate

        Returns:
            Tuple of (is_valid, message, model_info)
            - is_valid: Whether the API key is valid
            - message: Human-readable result message
            - model_info: Available models and account info if valid, None otherwise
        """
        if not api_key or not isinstance(api_key, str):
            return False, "API key cannot be empty", None

        if not api_key.startswith("sk-"):
            return False, "Invalid API key format. Must start with 'sk-'", None

        try:
            # Create OpenAI client with the provided API key
            client = OpenAI(api_key=api_key, timeout=self.timeout)

            # Test the API key by making a simple API call
            # We'll use the models endpoint as it's lightweight and requires valid auth
            logger.info("Testing OpenAI API key validation...")

            # Run the synchronous OpenAI call in a thread pool
            models_response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: client.models.list()
            )

            # If we get here, the API key is valid
            models_data = []
            available_models = []

            # Extract model information
            for model in models_response.data:
                model_info = {
                    "id": model.id,
                    "created": model.created,
                    "owned_by": model.owned_by,
                }
                models_data.append(model_info)
                available_models.append(model.id)

            # Focus on GPT models for the response
            gpt_models = [m for m in available_models if "gpt" in m.lower()]

            validation_info = {
                "total_models": len(available_models),
                "gpt_models": gpt_models[:10],  # Show first 10 GPT models
                "all_models_count": len(available_models),
                "key_valid": True,
            }

            logger.info(
                f"OpenAI API key validation successful. Found {len(available_models)} models"
            )

            return (
                True,
                f"API key is valid. Access to {len(available_models)} models confirmed.",
                validation_info,
            )

        except AuthenticationError as e:
            logger.warning(f"OpenAI API key authentication failed: {str(e)}")
            return False, "Invalid API key. Authentication failed with OpenAI.", None

        except RateLimitError as e:
            logger.warning(f"OpenAI API rate limit hit during validation: {str(e)}")
            # Rate limit doesn't mean the key is invalid, so we return True
            return (
                True,
                "API key appears valid but rate limited. Try again later.",
                {"rate_limited": True},
            )

        except APIConnectionError as e:
            logger.error(f"OpenAI API connection error during validation: {str(e)}")
            return (
                False,
                "Unable to connect to OpenAI API. Please try again later.",
                None,
            )

        except APIError as e:
            logger.error(f"OpenAI API error during validation: {str(e)}")
            # Check if it's a quota/billing issue
            if "quota" in str(e).lower() or "billing" in str(e).lower():
                return (
                    True,
                    "API key is valid but has quota/billing issues.",
                    {"quota_exceeded": True},
                )
            else:
                return False, f"OpenAI API error: {str(e)}", None

        except asyncio.TimeoutError:
            logger.error("OpenAI API validation timed out")
            return False, "Validation timed out. Please try again.", None

        except Exception as e:
            logger.error(f"Unexpected error during OpenAI API key validation: {str(e)}")
            return False, "Unexpected error during validation. Please try again.", None

    async def quick_validate_format(self, api_key: str) -> Tuple[bool, str]:
        """
        Quick format validation without making API calls.

        Args:
            api_key: The API key to validate

        Returns:
            Tuple of (is_valid, message)
        """
        if not api_key or not isinstance(api_key, str):
            return False, "API key cannot be empty"

        api_key = api_key.strip()

        if not api_key.startswith("sk-"):
            return False, "API key must start with 'sk-'"

        if len(api_key) < 40:
            return False, "API key appears too short"

        if len(api_key) > 200:
            return False, "API key appears too long"

        # Check for basic character validity
        allowed_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        )
        if not all(c in allowed_chars for c in api_key):
            return False, "API key contains invalid characters"

        return True, "API key format is valid"

    async def test_simple_completion(
        self, api_key: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Test API key with a simple completion to verify it works end-to-end.

        Args:
            api_key: The OpenAI API key to test

        Returns:
            Tuple of (success, message, response_info)
        """
        try:
            client = OpenAI(api_key=api_key, timeout=self.timeout)

            # Make a very simple, cheap completion request
            logger.info("Testing OpenAI API key with simple completion...")

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Say 'test successful'"}],
                    max_tokens=10,
                    temperature=0,
                ),
            )

            completion_info = {
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "response_preview": (
                    response.choices[0].message.content[:50]
                    if response.choices
                    else "No response"
                ),
            }

            logger.info("OpenAI API key completion test successful")
            return True, "API key successfully tested with completion", completion_info

        except AuthenticationError:
            return False, "Authentication failed - invalid API key", None
        except RateLimitError:
            return True, "API key valid but rate limited", {"rate_limited": True}
        except APIError as e:
            if "quota" in str(e).lower() or "billing" in str(e).lower():
                return (
                    True,
                    "API key valid but has quota/billing issues",
                    {"quota_exceeded": True},
                )
            return False, f"API error: {str(e)}", None
        except Exception as e:
            logger.error(f"Error testing completion: {str(e)}")
            return False, f"Test failed: {str(e)}", None


# Create global instance
openai_validation_service = OpenAIValidationService()
