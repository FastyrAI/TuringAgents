"""
Main FastAPI application.
Brings together all components and configurations.
"""

import sys
import os
from dotenv import load_dotenv

# Add current directory to Python path to support absolute imports
# This allows the app to run from the app directory with uvicorn main:app
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Load .env file from parent directory (project root)
# This ensures environment variables are loaded before any other imports
parent_dir = os.path.dirname(current_dir)
env_path = os.path.join(parent_dir, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    print(f" Warning: .env file not found at {env_path}")

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
import time
import logging

from core.config import settings
from core.database import check_database_connection
from core.exceptions import ComposioError
from api import api_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="A production-ready FastAPI web application with JWT authentication",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation error",
            "detail": exc.errors(),
            "error_type": "validation_error",
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail, "error_type": "http_error"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error_type": "internal_error",
        },
    )


@app.exception_handler(ComposioError)
async def composio_exception_handler(request: Request, exc: ComposioError):
    """Handle Composio-specific exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_type": "composio_error",
        },
    )

static_dir = os.path.join(current_dir, "static")
# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")
FileResponse(os.path.join(static_dir, "index.html"))
# Include API routes
app.include_router(api_router)


# Root endpoint - serve the UI
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint serving the main UI application.

    Returns:
        FileResponse: Main HTML file
    """
    return FileResponse("static/index.html")


# API info endpoint
@app.get("/api", tags=["root"])
async def api_info():
    """
    API information endpoint.

    Returns:
        dict: Application information and available endpoints
    """
    return {
        "message": "Welcome to FastAPI Authentication Demo",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "api": "/api/v1",
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    # Check database connection
    try:
        if check_database_connection():
            logger.info("Database connection verified successfully")
        else:
            logger.warning("Database connection check failed")
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        # Don't raise here, allow app to start but log the issue

    logger.info("FastAPI Authentication Demo started successfully!")


# Health check endpoint (root level for easy access)
@app.get("/health", tags=["health"])
async def health_check():
    """
    Basic health check endpoint.

    Returns:
        dict: Application health status
    """
    return {
        "status": "healthy",
        "message": "FastAPI Authentication Demo is running",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
    )
