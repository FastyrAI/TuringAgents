# API routes and endpoints
from fastapi import APIRouter
from .deps import get_db_session
from .health import router as health_router
from .v1 import api_v1_router

# Create main API router
api_router = APIRouter()

# Include health check routes
api_router.include_router(health_router)

# Include versioned API routes
api_router.include_router(api_v1_router)

__all__ = ["get_db_session", "api_router", "health_router", "api_v1_router"]
