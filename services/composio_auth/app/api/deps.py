"""
Shared dependencies for API endpoints.
Provides common dependencies like database sessions.
"""

from typing import Generator
from sqlalchemy.orm import Session

from core.database import get_db


def get_db_session() -> Generator[Session, None, None]:
    """
    Get database session dependency.

    Yields:
        Session: Database session

    Note:
        This is an alias for the core database get_db function
        for better organization and future extensibility.
    """
    yield from get_db()
