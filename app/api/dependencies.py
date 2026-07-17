"""FastAPI dependencies for validated filters and read-only database access."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_session_factory


@dataclass(frozen=True)
class AnalyticsFilters:
    """Optional fact-level filters shared by analytics endpoints."""

    start_date: date | None = None
    end_date: date | None = None
    region: str | None = None
    category: str | None = None
    subcategory: str | None = None


def get_analytics_filters(
    start_date: date | None = None,
    end_date: date | None = None,
    region: Annotated[str | None, Query(min_length=1, max_length=32)] = None,
    category: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    subcategory: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
) -> AnalyticsFilters:
    """Validate cross-field date order and normalize optional text filters."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_date must be on or before end_date",
        )
    return AnalyticsFilters(
        start_date=start_date,
        end_date=end_date,
        region=region.strip() if region else None,
        category=category.strip() if category else None,
        subcategory=subcategory.strip() if subcategory else None,
    )


def get_read_only_session() -> Generator[Session]:
    """Yield a transaction-scoped session that PostgreSQL enforces as read-only."""
    with get_session_factory()() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        try:
            yield session
        finally:
            session.rollback()
