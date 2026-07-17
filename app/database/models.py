"""Normalized SQLAlchemy models for retail sales and ETL auditing."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all RetailPulse database models."""


class TimestampMixin:
    """Created and updated timestamps shared by mutable business entities."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Customer(TimestampMixin, Base):
    """Current canonical customer attributes."""

    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    segment: Mapped[str] = mapped_column(String(64), nullable=False)
    country: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (Index("ix_customers_region", "region"),)


class Product(TimestampMixin, Base):
    """Current canonical product attributes."""

    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (Index("ix_products_category_subcategory", "category", "subcategory"),)


class EtlRun(Base):
    """Lifecycle and aggregate counts for one pipeline execution."""

    __tablename__ = "etl_runs"

    etl_run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    error_details: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_etl_runs_status"),
        CheckConstraint("total_rows >= 0", name="ck_etl_runs_total_rows"),
        CheckConstraint("valid_rows >= 0", name="ck_etl_runs_valid_rows"),
        CheckConstraint("invalid_rows >= 0", name="ck_etl_runs_invalid_rows"),
        CheckConstraint(
            "quality_score IS NULL OR quality_score BETWEEN 0 AND 100",
            name="ck_etl_runs_quality_score",
        ),
        Index("ix_etl_runs_status_started", "status", "started_at"),
        Index("ix_etl_runs_source_hash", "source_file_hash"),
    )


class Order(TimestampMixin, Base):
    """Order header separated from its product lines."""

    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="RESTRICT"), nullable=False
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    ship_date: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        CheckConstraint("ship_date >= order_date", name="ck_orders_ship_after_order"),
        Index("ix_orders_order_date", "order_date"),
        Index("ix_orders_customer_id", "customer_id"),
    )


class OrderItem(Base):
    """Retail fact row with a stable source-derived uniqueness key."""

    __tablename__ = "order_items"

    order_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_item_key: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id", ondelete="RESTRICT"), nullable=False
    )
    etl_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("etl_runs.etl_run_id", ondelete="RESTRICT"), nullable=False
    )
    source_file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    profit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("order_item_key", name="uq_order_items_order_item_key"),
        CheckConstraint("sales >= 0", name="ck_order_items_sales"),
        CheckConstraint("quantity > 0", name="ck_order_items_quantity"),
        CheckConstraint("discount BETWEEN 0 AND 1", name="ck_order_items_discount"),
        CheckConstraint("source_row_number >= 2", name="ck_order_items_source_row_number"),
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_product_id", "product_id"),
        Index("ix_order_items_etl_run_id", "etl_run_id"),
    )


class DataQualityResult(Base):
    """Detailed quality metrics associated one-to-one with an ETL run."""

    __tablename__ = "data_quality_results"

    data_quality_result_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    etl_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("etl_runs.etl_run_id", ondelete="CASCADE"), nullable=False
    )
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_order_ids: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_customer_ids: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_product_ids: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_dates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    negative_sales: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_quantities: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_discounts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_numeric_values: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown_regions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unreasonable_profit_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issue_counts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("etl_run_id", name="uq_data_quality_results_etl_run_id"),)


class RejectedRecord(Base):
    """Original source payload and all rejection reasons for an invalid row."""

    __tablename__ = "rejected_records"

    rejected_record_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    etl_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("etl_runs.etl_run_id", ondelete="CASCADE"), nullable=False
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rejection_reasons: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    original_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("source_row_number >= 2", name="ck_rejected_records_source_row_number"),
        Index("ix_rejected_records_etl_run_id", "etl_run_id"),
    )
