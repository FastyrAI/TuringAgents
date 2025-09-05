"""
Composio API endpoints for tool discovery, connection, and execution.
Handles natural language processing and external tool integrations.
"""

import os
from clients.composio_client import ComposioClient
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from sqlalchemy.orm import Session
from dependencies.auth import get_current_user
from models.user import User
from models.composio_connection import ComposioConnection
from services.composio_service import ComposioConnectionService, perform_action
from services.service_factory import get_user_openai_service
from schemas.composio import (
    ComposioConnectionList,
    ComposioConnection as ComposioConnectionSchema,
    ProviderEnum,
    ProviderInfo,
    ProvidersListResponse,
    ApiKeyConnectionRequest,
    ApiKeyConnectionResponse,
    ProviderAuthTypeResponse,
    AuthTypeEnum,
)
from core.database import get_db
from core.exceptions import ContentModerationError, ConfigurationError
from services.user_key_utils import UserKeyError
from core.input_validation import validate_and_sanitize_prompt, ValidationError
from core.rate_limiting import check_rate_limits
from clients.composio_client import ComposioClient
import logging


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/composio", tags=["composio"])


@router.get("/providers", response_model=ProvidersListResponse)
async def list_available_providers(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get list of available providers with connection status
    """
    # Apply rate limiting
    await check_rate_limits(request, ["composio_providers"])

    try:
        # Get available providers from Composio
        available_providers = ComposioClient().get_composio_providers()

        # Get user's existing connections
        user_connections = (
            db.query(ComposioConnection)
            .filter(ComposioConnection.user_id == user.id)
            .all()
        )

        # Create a mapping of connected providers
        connected_providers = {}
        for conn in user_connections:
            if conn.provider not in connected_providers:
                connected_providers[conn.provider] = []
            connected_providers[conn.provider].append(conn)

        # Build provider info list (simplified - only name and connection status)
        providers_info = []
        for provider_name in available_providers:
            connected_conns = connected_providers.get(provider_name, [])
            is_connected = len(connected_conns) > 0
            last_connected = None

            if connected_conns:
                # Get the most recent connection
                latest_conn = max(connected_conns, key=lambda x: x.created_at)
                last_connected = latest_conn.created_at.isoformat()

            # Get auth type for this provider
            try:
                auth_type = ComposioClient().get_provider_auth_type(provider_name)
            except Exception:
                # Default fallback
                auth_type = "oauth"

            provider_info = ProviderInfo(
                name=provider_name,
                display_name=provider_name.title(),  # Simple capitalization
                description=f"{provider_name.title()} integration",  # Minimal description
                connected=is_connected,
                connection_count=len(connected_conns),
                last_connected=last_connected,
                status="connected" if is_connected else "available",
                auth_type=auth_type,
                requires_redirect=(auth_type == "oauth2"),
            )
            providers_info.append(provider_info)

        # Sort providers: connected first, then by display name
        providers_info.sort(key=lambda p: (not p.connected, p.display_name))

        logger.info(f"Listed {len(providers_info)} providers for user {user.id}")

        return ProvidersListResponse(
            providers=providers_info, total=len(providers_info)
        )

    except Exception as e:
        logger.error(f"Failed to list providers for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve available providers"
        )


@router.get("/connections", response_model=ComposioConnectionList)
async def list_connections(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all composio connections for the authenticated user
    """
    # Apply rate limiting
    await check_rate_limits(request, ["composio_connections"])

    try:
        connections = (
            db.query(ComposioConnection)
            .filter(ComposioConnection.user_id == user.id)
            .all()
        )

        logger.info(f"Listed {len(connections)} connections for user {user.id}")

        return ComposioConnectionList(
            connections=[
                ComposioConnectionSchema.from_orm(conn) for conn in connections
            ],
            total=len(connections),
        )

    except Exception as e:
        logger.error(f"Failed to list connections for user {user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve connections")


@router.post("/auth/provider/")
async def auth(
    request: Request,
    provider: ProviderEnum = Query(
        ..., description="Provider to connect", example="gmail"
    ),
    auth_type: AuthTypeEnum = Query(
        ..., description="Authentication type: 'oauth2' or 'api_key'"
    ),
    api_key: str = Form(None, description="API key for api_key authentication"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Connect to a provider using either OAuth or API key authentication.

    **Parameters:**
    - **provider**: Provider identifier (e.g., 'gmail', 'coda')
    - **auth_type**: Authentication type ('oauth2' for OAuth flow, 'api_key' for API key)
    - **api_key**: Required only for API key authentication

    **Returns:**
    - For OAuth: auth_url to redirect user
    - For API key: success confirmation

    **Examples:**
    ```
    POST /api/v1/composio/auth/provider/?provider=gmail&auth_type=oauth2
    POST /api/v1/composio/auth/provider/?provider=coda&auth_type=api_key
    (with api_key in form data)
    ```
    """
    # Apply rate limiting
    await check_rate_limits(request, ["composio_auth"])

    if auth_type == "oauth2":
        try:
            # Get auth URL for OAuth flow
            connection = ComposioConnectionService(db, str(user.id), provider.value)
            auth_response = connection.get_auth_url()
            connection.save_to_db(auth_response)
            logger.info(
                f"Generated OAuth URL for user {user.id} and provider {provider.value}"
            )
            return {"auth_url": auth_response.redirect_url}

        except ValueError as e:
            logger.error(f"Configuration error for OAuth: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Configuration error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to initiate OAuth for user {user.id}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to initiate OAuth: {str(e)}"
            )

    elif auth_type == "api_key":
        # Validate API key is provided
        if not api_key:
            raise HTTPException(
                status_code=400, detail="API key is required for api_key authentication"
            )

        try:
            # Connect using API key
            connection = ComposioConnectionService(
                db, str(user.id), provider.value, api_key
            )
            response = connection.connect_with_api_key()
            connection.save_to_db(response)

            logger.info(
                f"API key connection successful for user {user.id} and provider {provider.value}"
            )

            return {
                "success": True,
                "message": f"Successfully connected to {provider.value}",
                "connection_id": response.id if hasattr(response, "id") else None,
            }

        except ValueError as e:
            logger.error(f"API key connection configuration error: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Configuration error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to connect with API key for user {user.id}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to connect with API key: {str(e)}"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid auth_type '{auth_type}'. Must be 'oauth2' or 'api_key'",
        )


@router.post("/action")
async def action(
    request: Request,
    prompt: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Execute natural language action via Composio with enhanced security validation.
    Requires users to have their own OpenAI API keys configured.
    
    Args:
        prompt: Natural language description of the action to execute
    """
    # Apply rate limiting (most restrictive for expensive operations)
    await check_rate_limits(request, ["composio_action"])

    try:
        # Validate and sanitize prompt
        validated_prompt = validate_and_sanitize_prompt(prompt)

        # Get user-specific OpenAI service for content moderation
        # Require user to have their own API key
        user_openai_service = get_user_openai_service(user, db, require_user_key=True)

        # Check for hostile content before processing using user's service
        is_flagged, hostilities = user_openai_service.hostile_message_check(
            validated_prompt
        )

        if is_flagged:
            logger.warning(
                f"Content moderation flagged prompt from user {user.id}: {hostilities}"
            )
            raise ContentModerationError(hostilities)

        # Log the action for security monitoring
        logger.info(f"Executing action for user {user.id}: {validated_prompt[:100]}...")

        # If content is safe, proceed with normal processing (pass db session for user key access)
        result = perform_action(str(user.id), validated_prompt, db_session=db)

        logger.info(f"Action completed successfully for user {user.id}")
        return result

    except ValidationError as e:
        logger.warning(
            f"Validation error for action request from user {user.id}: {str(e)}"
        )
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except ContentModerationError:
        # Re-raise content moderation errors as-is
        raise
    except (UserKeyError, ConfigurationError) as e:
        logger.warning(f"API key error for user {user.id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Action execution failed for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to execute action. Please try again later."
        )
