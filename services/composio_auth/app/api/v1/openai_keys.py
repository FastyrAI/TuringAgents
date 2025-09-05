"""
OpenAI API key management endpoints.
Handles CRUD operations for user OpenAI API keys with enhanced security.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import logging

from core.rate_limiting import check_rate_limits
from core.input_validation import ValidationError
from crud.openai_key import openai_key_crud
from schemas.openai_key import (
    OpenAIKeyCreate,
    OpenAIKeyUpdate,
    OpenAIKeyResponse,
    OpenAIKeyStatusResponse,
)
from services.openai_validation_service import openai_validation_service
from api.deps import get_db_session
from dependencies.auth import get_current_user
from models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/openai-keys", tags=["openai-keys"])


@router.post(
    "/", response_model=OpenAIKeyStatusResponse, status_code=status.HTTP_201_CREATED
)
async def create_openai_key(
    request: Request,
    openai_key_data: OpenAIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OpenAIKeyStatusResponse:
    """
    Create/store a new OpenAI API key for the authenticated user.

    **Security**: API keys are automatically validated against OpenAI's API before being stored.

    Args:
        request: FastAPI request object for rate limiting
        openai_key_data: OpenAI API key creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        OpenAIKeyStatusResponse: Success response with API key data (masked)

    Raises:
        HTTPException: If creation fails or validation fails
    """
    # Apply rate limiting
    await check_rate_limits(request, ["openai_key_create"])

    try:
        # Always validate API key before storing
        logger.info(f"Validating API key before storing for user {current_user.id}")
        is_valid, validation_message, model_info = (
            await openai_validation_service.validate_api_key(openai_key_data.api_key)
        )

        if not is_valid:
            logger.warning(
                f"API key validation failed for user {current_user.id}: {validation_message}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"API key validation failed: {validation_message}",
            )

        logger.info(f"API key validation successful for user {current_user.id}")

        # Create the API key
        db_openai_key = openai_key_crud.create(
            db=db, user_id=current_user.id, openai_key_create=openai_key_data
        )

        # Get response format with key preview
        key_response = openai_key_crud.get_user_key_response(db, current_user.id)

        logger.info(f"OpenAI API key created successfully for user {current_user.id}")

        return OpenAIKeyStatusResponse(
            success=True,
            message="OpenAI API key created successfully",
            data=key_response,
        )

    except ValueError as e:
        logger.warning(
            f"Validation error creating OpenAI key for user {current_user.id}: {str(e)}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(
            f"Failed to create OpenAI key for user {current_user.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create OpenAI API key",
        )


@router.get("/", response_model=OpenAIKeyStatusResponse, status_code=status.HTTP_200_OK)
async def get_openai_key(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OpenAIKeyStatusResponse:
    """
    Get the authenticated user's OpenAI API key information.

    Returns the API key details with a masked preview for security.

    Args:
        request: FastAPI request object for rate limiting
        current_user: Current authenticated user
        db: Database session

    Returns:
        OpenAIKeyStatusResponse: API key data with masked preview

    Raises:
        HTTPException: If no API key is found
    """
    # Apply rate limiting
    await check_rate_limits(request, ["openai_key_read"])

    try:
        # Get user's API key
        key_response = openai_key_crud.get_user_key_response(db, current_user.id)

        if not key_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No OpenAI API key found. Please create one first.",
            )

        logger.info(f"OpenAI API key retrieved for user {current_user.id}")

        return OpenAIKeyStatusResponse(
            success=True,
            message="OpenAI API key retrieved successfully",
            data=key_response,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Failed to retrieve OpenAI key for user {current_user.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve OpenAI API key",
        )


@router.put("/", response_model=OpenAIKeyStatusResponse, status_code=status.HTTP_200_OK)
async def update_openai_key(
    request: Request,
    openai_key_update: OpenAIKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OpenAIKeyStatusResponse:
    """
    Update the authenticated user's OpenAI API key.

    You can update the API key itself.
    **Security**: New API keys are automatically validated against OpenAI's API before being stored.

    Args:
        request: FastAPI request object for rate limiting
        openai_key_update: Update data for the API key
        current_user: Current authenticated user
        db: Database session

    Returns:
        OpenAIKeyStatusResponse: Success response with updated API key data

    Raises:
        HTTPException: If update fails, validation fails, or no API key exists
    """
    # Apply rate limiting
    await check_rate_limits(request, ["openai_key_update"])

    try:
        # Always validate new API key if provided
        if openai_key_update.api_key:
            logger.info(
                f"Validating new API key before updating for user {current_user.id}"
            )
            is_valid, validation_message, model_info = (
                await openai_validation_service.validate_api_key(
                    openai_key_update.api_key
                )
            )

            if not is_valid:
                logger.warning(
                    f"API key validation failed for user {current_user.id}: {validation_message}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"API key validation failed: {validation_message}",
                )

            logger.info(f"API key validation successful for user {current_user.id}")

        # Update the API key
        updated_key = openai_key_crud.update(
            db=db, user_id=current_user.id, openai_key_update=openai_key_update
        )

        if not updated_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No OpenAI API key found to update. Please create one first.",
            )

        # Get response format with key preview
        key_response = openai_key_crud.get_user_key_response(db, current_user.id)

        logger.info(f"OpenAI API key updated successfully for user {current_user.id}")

        return OpenAIKeyStatusResponse(
            success=True,
            message="OpenAI API key updated successfully",
            data=key_response,
        )

    except ValueError as e:
        logger.warning(
            f"Validation error updating OpenAI key for user {current_user.id}: {str(e)}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Failed to update OpenAI key for user {current_user.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update OpenAI API key",
        )


@router.delete(
    "/", response_model=OpenAIKeyStatusResponse, status_code=status.HTTP_200_OK
)
async def delete_openai_key(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OpenAIKeyStatusResponse:
    """
    Delete the authenticated user's OpenAI API key.

    **Warning**: This action cannot be undone. The API key will be permanently deleted.

    Args:
        request: FastAPI request object for rate limiting
        current_user: Current authenticated user
        db: Database session

    Returns:
        OpenAIKeyStatusResponse: Success response confirming deletion (data=None)

    Raises:
        HTTPException: If deletion fails or no API key exists
    """
    # Apply rate limiting
    await check_rate_limits(request, ["openai_key_delete"])

    try:
        # Delete the API key
        deleted = openai_key_crud.delete(db=db, user_id=current_user.id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No OpenAI API key found to delete.",
            )

        logger.info(f"OpenAI API key deleted successfully for user {current_user.id}")

        return OpenAIKeyStatusResponse(
            success=True, message="OpenAI API key deleted successfully", data=None
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete OpenAI key for user {current_user.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete OpenAI API key",
        )


@router.post(
    "/toggle", response_model=OpenAIKeyStatusResponse, status_code=status.HTTP_200_OK
)
async def toggle_openai_key_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OpenAIKeyStatusResponse:
    """
    Toggle the active status of the authenticated user's OpenAI API key.

    This allows you to temporarily disable/enable your API key without deleting it.

    Args:
        request: FastAPI request object for rate limiting
        current_user: Current authenticated user
        db: Database session

    Returns:
        OpenAIKeyStatusResponse: Success response with updated API key data

    Raises:
        HTTPException: If toggle fails or no API key exists
    """
    # Apply rate limiting
    await check_rate_limits(request, ["openai_key_update"])

    try:
        # Toggle the API key status
        updated_key = openai_key_crud.toggle_active_status(
            db=db, user_id=current_user.id
        )

        if not updated_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No OpenAI API key found to toggle.",
            )

        # Get response format with key preview
        key_response = openai_key_crud.get_user_key_response(db, current_user.id)

        status_text = "activated" if updated_key.is_active else "deactivated"
        logger.info(f"OpenAI API key {status_text} for user {current_user.id}")

        return OpenAIKeyStatusResponse(
            success=True,
            message=f"OpenAI API key {status_text} successfully",
            data=key_response,
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Failed to toggle OpenAI key status for user {current_user.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle OpenAI API key status",
        )
