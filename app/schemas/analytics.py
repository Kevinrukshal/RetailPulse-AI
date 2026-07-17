"""Pydantic v2 analytics response models."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SummaryResponse(BaseModel):
    """Executive KPI summary."""

    total_revenue: float
    total_profit: float
    profit_margin: float
    total_orders: int
    unique_customers: int
    average_order_value: float
    average_units_per_order: float


class MonthlyPerformanceResponse(BaseModel):
    """Monthly revenue, profit, and growth."""

    month_start: date
    revenue: float
    profit: float
    profit_margin: float | None
    units: int
    orders: int
    customers: int
    month_over_month_growth_pct: float | None
    year_over_year_growth_pct: float | None


class ProductPerformanceResponse(BaseModel):
    """Ranked product performance row."""

    product_id: str
    product_name: str
    category: str
    subcategory: str
    revenue: float
    profit: float
    profit_margin: float | None
    units: int
    orders: int
    average_discount: float


class CustomerPerformanceResponse(BaseModel):
    """Customer lifetime and RFM metrics."""

    customer_id: str
    customer_name: str
    segment: str
    region: str
    lifetime_revenue: float
    lifetime_profit: float
    purchase_frequency: int
    last_purchase_date: date
    average_order_value: float
    recency_days: int
    rfm_segment: str


class CustomerSegmentResponse(BaseModel):
    """Aggregated RFM segment performance."""

    rfm_segment: str
    customers: int
    revenue: float
    profit: float


class RegionalPerformanceResponse(BaseModel):
    """Regional KPI row."""

    region: str
    revenue: float
    profit: float
    profit_margin: float | None
    orders: int
    customers: int
    units: int


class ProfitLeakageResponse(BaseModel):
    """One line requiring margin investigation."""

    order_item_key: str
    order_id: str
    order_date: date
    region: str
    product_id: str
    product_name: str
    category: str
    subcategory: str
    sales: float
    profit: float
    profit_margin: float | None
    discount: float
    quantity: int
    leakage_reason: str


class DataQualityResponse(BaseModel):
    """Latest completed ETL quality record."""

    etl_run_id: UUID
    source_file: str
    started_at: datetime
    completed_at: datetime
    total_rows: int
    valid_rows: int
    invalid_rows: int
    quality_score: float
    issue_counts: dict[str, int]


class EtlRunResponse(BaseModel):
    """ETL run history item."""

    etl_run_id: UUID
    source_file: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None
    total_rows: int
    valid_rows: int
    invalid_rows: int
    quality_score: float | None
    error_details: str | None


class EtlRunPageResponse(BaseModel):
    """Offset-paginated ETL history."""

    items: list[EtlRunResponse]
    total: int
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class ErrorResponse(BaseModel):
    """Safe API error body."""

    detail: str
    context: dict[str, Any] | None = None
