"""
Health check API endpoints.
Monitors application and database health.
"""

import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from core.database import check_database_connection
from api.deps import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def full_health_check(db: Session = Depends(get_db_session)) -> dict:
    """
    Comprehensive health check endpoint.

    Args:
        db: Database session

    Returns:
        dict: Health status with keys: status, timestamp, services (application, database), message
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.datetime.now(),
        "services": {"application": "healthy", "database": "unknown"},
    }

    # Check database health
    try:
        db_healthy = check_database_connection()
        health_status["services"]["database"] = "healthy" if db_healthy else "unhealthy"

        if not db_healthy:
            health_status["status"] = "degraded"

    except Exception:
        health_status["services"]["database"] = "unhealthy"
        health_status["status"] = "degraded"

    # Set overall status
    if health_status["status"] == "degraded":
        health_status["message"] = (
            "Application is running but some services are degraded"
        )
    else:
        health_status["message"] = "All services are healthy"

    return health_status
