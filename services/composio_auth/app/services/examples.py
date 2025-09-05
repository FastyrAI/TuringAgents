"""
Examples of how to use the user key utilities and service factory.
This file demonstrates various patterns for accessing user-specific API keys.
"""

from sqlalchemy.orm import Session
from ..models.user import User


def example_basic_key_access(user_id: int, db_session: Session):
    """Example: Basic way to get user's API key."""
    from .user_key_utils import get_user_openai_key, UserKeyNotFoundError

    try:
        api_key = get_user_openai_key(user_id, db_session)
        print(f"User has API key: {api_key[:10]}...")
    except UserKeyNotFoundError:
        print("User doesn't have an API key")


def example_safe_key_access(user_id: int, db_session: Session, global_key: str):
    """Example: Safe access with fallback."""
    from .user_key_utils import get_user_openai_key_safe

    api_key = get_user_openai_key_safe(user_id, db_session, fallback_key=global_key)
    if api_key:
        print(f"Using API key: {api_key[:10]}...")
    else:
        print("No API key available")


def example_check_before_use(user_id: int, db_session: Session):
    """Example: Check if user has key before proceeding."""
    from .user_key_utils import check_user_has_openai_key

    has_key, error = check_user_has_openai_key(user_id, db_session)
    if has_key:
        print("User can use OpenAI features")
        # Proceed with OpenAI operations
    else:
        print(f"Cannot use OpenAI: {error}")


def example_context_manager(user_id: int, db_session: Session):
    """Example: Using context manager for automatic usage tracking."""
    from .user_key_utils import UserOpenAIKeyContext, UserKeyNotFoundError

    try:
        with UserOpenAIKeyContext(user_id, db_session) as api_key:
            # Use api_key for OpenAI operations
            # last_used_at will be automatically updated
            print(f"Using API key in context: {api_key[:10]}...")
    except UserKeyNotFoundError:
        print("User doesn't have an API key")


@require_user_openai_key("This feature requires an OpenAI API key")
def example_decorated_function(user_id: int, db_session: Session, prompt: str):
    """Example: Function that requires user to have API key."""
    # This function will only be called if user has a valid API key
    print(f"Processing prompt for user {user_id}: {prompt}")


def example_service_factory(user: User, db_session: Session):
    """Example: Using service factory for high-level access."""
    from .service_factory import create_user_service_factory

    factory = create_user_service_factory(user, db_session)

    # Get service capabilities
    capabilities = factory.get_service_capabilities()
    print(f"OpenAI available: {capabilities['openai']['available']}")
    print(f"Using user key: {capabilities['openai']['using_user_key']}")

    # Create OpenAI service
    try:
        openai_service = factory.create_openai_service(require_user_key=False)
        print(f"OpenAI service created: {openai_service.get_api_key_info()}")
    except Exception as e:
        print(f"Could not create OpenAI service: {e}")


def example_convenience_function(user: User, db_session: Session):
    """Example: Using convenience function."""
    from .service_factory import get_user_openai_service

    # Get OpenAI service with fallback to global key
    openai_service = get_user_openai_service(user, db_session, require_user_key=False)

    # Check what type of key it's using
    key_info = openai_service.get_api_key_info()
    if key_info["using_key_type"] == "user":
        print("Using user's own API key")
    elif key_info["using_key_type"] == "global":
        print("Using global API key")
    else:
        print("No API key available")


def example_validation(user: User, db_session: Session):
    """Example: Validating user access to services."""
    from .service_factory import validate_user_service_access

    result = validate_user_service_access(user, db_session, "openai")

    if result["can_access"]:
        print(f"User can access OpenAI: {result['reason']}")
    else:
        print(f"User cannot access OpenAI: {result['reason']}")
        print("Suggestions:")
        for suggestion in result["suggestions"]:
            print(f"  - {suggestion}")


# Usage patterns summary:
"""
1. Direct key access:
   - get_user_openai_key() - Get key or raise exception
   - get_user_openai_key_safe() - Get key with fallback
   - check_user_has_openai_key() - Check availability

2. Context management:
   - UserOpenAIKeyContext - Automatic usage tracking
   - @require_user_openai_key - Decorator for functions

3. Service creation:
   - ServiceFactory - Full-featured factory
   - get_user_openai_service() - Convenience function
   - OpenAIService.create_with_user() - Direct instantiation

4. Validation:
   - validate_user_can_use_openai() - Validate access
   - validate_user_service_access() - Service-specific validation
"""
