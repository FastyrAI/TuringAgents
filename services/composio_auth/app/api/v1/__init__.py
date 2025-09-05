# API Version 1 routes
from fastapi import APIRouter
from .auth import router as auth_router

# from .users import router as users_router
from api.v1.composio import router as composio_router
from api.v1.openai_keys import router as openai_keys_router

# Create main v1 router
api_v1_router = APIRouter(prefix="/api/v1")

# Include all route modules
api_v1_router.include_router(auth_router)
# api_v1_router.include_router(users_router)
api_v1_router.include_router(composio_router)
api_v1_router.include_router(openai_keys_router)

__all__ = ["api_v1_router"]
