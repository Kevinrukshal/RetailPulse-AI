"""Versioned read-only retail analytics routes."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import AnalyticsFilters, get_analytics_filters, get_read_only_session
from app.schemas.analytics import (
    CustomerPerformanceResponse,
    CustomerSegmentResponse,
    DataQualityResponse,
    EtlRunPageResponse,
    MonthlyPerformanceResponse,
    ProductPerformanceResponse,
    ProfitLeakageResponse,
    RegionalPerformanceResponse,
    SummaryResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1")
ReadOnlySession = Annotated[Session, Depends(get_read_only_session)]
Filters = Annotated[AnalyticsFilters, Depends(get_analytics_filters)]


@router.get("/summary", response_model=SummaryResponse, tags=["Executive"])
def summary(filters: Filters, session: ReadOnlySession) -> dict:
    """Return filtered executive KPIs."""
    return AnalyticsService(session).summary(filters)


@router.get(
    "/revenue/monthly",
    response_model=list[MonthlyPerformanceResponse],
    tags=["Revenue"],
)
def monthly_revenue(filters: Filters, session: ReadOnlySession) -> list[dict]:
    """Return filtered monthly revenue, profit, and growth."""
    return AnalyticsService(session).monthly(filters)


@router.get("/products/top", response_model=list[ProductPerformanceResponse], tags=["Products"])
def top_products(
    filters: Filters,
    session: ReadOnlySession,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    sort_by: Literal["revenue", "profit", "units"] = "revenue",
) -> list[dict]:
    """Return top products by an allowlisted metric."""
    return AnalyticsService(session).products(
        filters, limit=limit, sort_by=sort_by, loss_making_only=False
    )


@router.get(
    "/products/loss-making",
    response_model=list[ProductPerformanceResponse],
    tags=["Products"],
)
def loss_making_products(
    filters: Filters,
    session: ReadOnlySession,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[dict]:
    """Return products whose filtered aggregate profit is negative."""
    return AnalyticsService(session).products(
        filters, limit=limit, sort_by="profit", loss_making_only=True
    )


@router.get(
    "/customers/top",
    response_model=list[CustomerPerformanceResponse],
    tags=["Customers"],
)
def top_customers(
    session: ReadOnlySession,
    region: Annotated[str | None, Query(min_length=1, max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    sort_by: Literal[
        "lifetime_revenue", "lifetime_profit", "purchase_frequency"
    ] = "lifetime_revenue",
) -> list[dict]:
    """Return customer lifetime metrics and RFM classification."""
    return AnalyticsService(session).customers(region=region, limit=limit, sort_by=sort_by)


@router.get(
    "/customers/segments",
    response_model=list[CustomerSegmentResponse],
    tags=["Customers"],
)
def customer_segments(
    session: ReadOnlySession,
    region: Annotated[str | None, Query(min_length=1, max_length=32)] = None,
) -> list[dict]:
    """Aggregate lifetime performance by RFM segment."""
    return AnalyticsService(session).customer_segments(region=region)


@router.get(
    "/regions/performance",
    response_model=list[RegionalPerformanceResponse],
    tags=["Regions"],
)
def region_performance(filters: Filters, session: ReadOnlySession) -> list[dict]:
    """Return regional metrics with optional date and product filters."""
    return AnalyticsService(session).regions(filters)


@router.get(
    "/profit-leakage",
    response_model=list[ProfitLeakageResponse],
    tags=["Profit Leakage"],
)
def profit_leakage(
    filters: Filters,
    session: ReadOnlySession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict]:
    """Return loss-making, excessive-discount, or weak-margin lines."""
    return AnalyticsService(session).leakage(filters, limit=limit)


@router.get(
    "/data-quality/latest",
    response_model=DataQualityResponse,
    tags=["Data Quality"],
)
def latest_data_quality(session: ReadOnlySession) -> dict:
    """Return the latest completed ETL quality result."""
    return AnalyticsService(session).latest_quality()


@router.get("/etl-runs", response_model=EtlRunPageResponse, tags=["Data Quality"])
def etl_runs(
    session: ReadOnlySession,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """Return paginated pipeline execution history."""
    return AnalyticsService(session).etl_runs(limit=limit, offset=offset)
