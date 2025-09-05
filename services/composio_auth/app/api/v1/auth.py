"""
Authentication API endpoints.
Handles user registration and login with enhanced security.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import logging

from core.security import (
    create_user_token,
    validate_password_strength,
    track_failed_login,
    is_account_locked,
    clear_failed_attempts,
    blacklist_token,
)
from core.config import settings
from core.rate_limiting import check_rate_limits
from core.input_validation import ValidationError, InputValidator
from crud.user import user_crud
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse, AuthResponse
from schemas.user import UserResponse, UserCreate
from api.deps import get_db_session
from dependencies.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    request: Request, user_data: RegisterRequest, db: Session = Depends(get_db_session)
) -> AuthResponse:
    """
    Register a new user with enhanced security validation.

    Args:
        request: FastAPI request object for rate limiting
        user_data: User registration data
        db: Database session

    Returns:
        AuthResponse: Success response with user data and token

    Raises:
        HTTPException: If registration fails
    """
    # Apply rate limiting
    await check_rate_limits(request, ["auth_register"])

    # Additional input validation
    validated_name = InputValidator.validate_name(user_data.name)
    validated_email = InputValidator.validate_email(user_data.email)
    validated_username = InputValidator.validate_username(user_data.username)

    # Validate password strength
    is_valid, error_message = validate_password_strength(user_data.password)
    if not is_valid:
        logger.warning(f"Weak password attempted for registration: {validated_email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
        )

    # Create updated user data with validated fields
    validated_user_data = UserCreate(
        name=validated_name,
        email=validated_email,
        username=validated_username,
        password=user_data.password,
    )

    # Create user in database
    db_user = user_crud.create(db, user_create=validated_user_data)

    # Generate JWT token with session tracking
    access_token = create_user_token(db_user.id, create_session=True)

    # Create response
    token_response = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes
        * 60,  # Convert minutes to seconds
    )

    logger.info(f"User registered successfully: {validated_email}")

    return AuthResponse(
        success=True, message="User registered successfully", data=token_response
    )


@router.post("/login", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def login(
    request: Request, login_data: LoginRequest, db: Session = Depends(get_db_session)
) -> AuthResponse:
    """
    Authenticate user and return JWT token with enhanced security.

    Args:
        request: FastAPI request object for rate limiting
        login_data: User login credentials
        db: Database session

    Returns:
        AuthResponse: Success response with authentication token

    Raises:
        HTTPException: If authentication fails
    """
    # Apply rate limiting
    await check_rate_limits(request, ["auth_login"])

    try:
        # Validate email format
        validated_email = InputValidator.validate_email(login_data.email)

        # Check if account is locked due to failed attempts
        is_locked, remaining_time = is_account_locked(validated_email)
        if is_locked:
            logger.warning(f"Login attempt for locked account: {validated_email}")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account temporarily locked due to failed login attempts. Try again in {remaining_time} seconds.",
            )

        # Authenticate user
        user = user_crud.authenticate(
            db, email=validated_email, password=login_data.password
        )

        if not user:
            # Track failed login attempt
            should_lock = track_failed_login(validated_email)

            if should_lock:
                logger.warning(
                    f"Account locked due to repeated failed attempts: {validated_email}"
                )
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account temporarily locked due to repeated failed login attempts.",
                )
            else:
                logger.warning(f"Failed login attempt for: {validated_email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                )

        # Clear failed attempts on successful login
        clear_failed_attempts(validated_email)

        # Generate JWT token with session tracking
        access_token = create_user_token(user.id, create_session=True)

        # Create response
        token_response = TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes
            * 60,  # Convert minutes to seconds
        )

        logger.info(f"Successful login for user: {validated_email}")

        return AuthResponse(
            success=True, message="Login successful", data=token_response
        )

    except ValidationError as e:
        logger.warning(f"Validation error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid input: {str(e)}"
        )
    except HTTPException:
        # Re-raise HTTP exceptions (including our custom ones)
        raise
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Login failed with unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login",
        )


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_current_user_info(
    request: Request, current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """
    Get current authenticated user information.

    Args:
        request: FastAPI request object for rate limiting
        current_user: Current authenticated user from dependency

    Returns:
        UserResponse: Current user information
    """
    # Apply rate limiting
    await check_rate_limits(request, ["auth_me"])

    logger.info(f"User info requested for user: {current_user.id}")
    return current_user


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request, current_user: UserResponse = Depends(get_current_user)
):
    """
    Logout endpoint with proper token invalidation.

    Args:
        request: FastAPI request object for rate limiting
        current_user: Current authenticated user from dependency

    Returns:
        dict: Success message
    """
    # Apply rate limiting
    await check_rate_limits(request, ["auth_me"])  # Use same limit as /me endpoint

    try:
        # Extract token from request headers
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

            # Blacklist the current token
            success = blacklist_token(token)

            if success:
                logger.info(f"User logged out successfully: {current_user.id}")
                return {
                    "success": True,
                    "message": "Logout successful. Token has been invalidated.",
                }
            else:
                logger.warning(
                    f"Failed to blacklist token during logout for user: {current_user.id}"
                )
                return {
                    "success": True,
                    "message": "Logout successful. Please remove the token from client storage.",
                }
        else:
            logger.warning(
                f"No valid token found during logout for user: {current_user.id}"
            )
            return {
                "success": True,
                "message": "Logout successful. No token to invalidate.",
            }

    except Exception as e:
        logger.error(f"Error during logout for user {current_user.id}: {str(e)}")
        # Even if blacklisting fails, we can still return success
        # as the client should remove the token anyway
        return {
            "success": True,
            "message": "Logout successful. Please remove the token from client storage.",
        }
