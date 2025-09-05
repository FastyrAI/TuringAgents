# Services package for external integrations
# from .composio_service import composio_client
from .openai_service import (
    OpenAIService,
    get_openai_service_for_user,
    get_global_openai_service,
)
from .openai_validation_service import (
    openai_validation_service,
    OpenAIValidationService,
)
from .user_key_utils import (
    get_user_openai_key,
    check_user_has_openai_key,
    get_user_openai_key_safe,
    update_user_key_usage,
    get_user_key_info,
    require_user_openai_key,
    UserOpenAIKeyContext,
    validate_user_can_use_openai,
    get_openai_service_config,
    UserKeyError,
    UserKeyNotFoundError,
    UserKeyInactiveError,
)
from .service_factory import (
    ServiceFactory,
    create_user_service_factory,
    get_user_openai_service,
    validate_user_service_access,
)

__all__ = [
    # "composio_client",
    "OpenAIService",
    "get_openai_service_for_user",
    "get_global_openai_service",
    "openai_validation_service",
    "OpenAIValidationService",
    # User key utilities
    "get_user_openai_key",
    "check_user_has_openai_key",
    "get_user_openai_key_safe",
    "update_user_key_usage",
    "get_user_key_info",
    "require_user_openai_key",
    "UserOpenAIKeyContext",
    "validate_user_can_use_openai",
    "get_openai_service_config",
    "UserKeyError",
    "UserKeyNotFoundError",
    "UserKeyInactiveError",
    # Service factory
    "ServiceFactory",
    "create_user_service_factory",
    "get_user_openai_service",
    "validate_user_service_access",
]
