"""Create normalized retail and ETL audit schema.

Revision ID: 0001_initial_schema
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create business entities, facts, and ETL audit tables."""
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.String(64), primary_key=True),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("segment", sa.String(64), nullable=False),
        sa.Column("country", sa.String(128), nullable=False),
        sa.Column("city", sa.String(128), nullable=False),
        sa.Column("state", sa.String(128), nullable=False),
        sa.Column("region", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_customers_region", "customers", ["region"])

    op.create_table(
        "products",
        sa.Column("product_id", sa.String(64), primary_key=True),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("subcategory", sa.String(128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_products_category_subcategory", "products", ["category", "subcategory"])

    op.create_table(
        "etl_runs",
        sa.Column("etl_run_id", sa.Uuid(), primary_key=True),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("source_file_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Numeric(14, 3)),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Numeric(5, 2)),
        sa.Column("error_details", sa.Text()),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')", name="ck_etl_runs_status"
        ),
        sa.CheckConstraint("total_rows >= 0", name="ck_etl_runs_total_rows"),
        sa.CheckConstraint("valid_rows >= 0", name="ck_etl_runs_valid_rows"),
        sa.CheckConstraint("invalid_rows >= 0", name="ck_etl_runs_invalid_rows"),
        sa.CheckConstraint(
            "quality_score IS NULL OR quality_score BETWEEN 0 AND 100",
            name="ck_etl_runs_quality_score",
        ),
    )
    op.create_index("ix_etl_runs_source_hash", "etl_runs", ["source_file_hash"])
    op.create_index("ix_etl_runs_status_started", "etl_runs", ["status", "started_at"])

    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(64), primary_key=True),
        sa.Column(
            "customer_id",
            sa.String(64),
            sa.ForeignKey("customers.customer_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("ship_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("ship_date >= order_date", name="ck_orders_ship_after_order"),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_order_date", "orders", ["order_date"])

    op.create_table(
        "order_items",
        sa.Column("order_item_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("order_item_key", sa.String(64), nullable=False),
        sa.Column(
            "order_id",
            sa.String(64),
            sa.ForeignKey("orders.order_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.String(64),
            sa.ForeignKey("products.product_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "etl_run_id",
            sa.Uuid(),
            sa.ForeignKey("etl_runs.etl_run_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_file_hash", sa.String(64), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("sales", sa.Numeric(14, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("discount", sa.Numeric(7, 6), nullable=False),
        sa.Column("profit", sa.Numeric(14, 2), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("order_item_key", name="uq_order_items_order_item_key"),
        sa.CheckConstraint("sales >= 0", name="ck_order_items_sales"),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity"),
        sa.CheckConstraint("discount BETWEEN 0 AND 1", name="ck_order_items_discount"),
        sa.CheckConstraint("source_row_number >= 2", name="ck_order_items_source_row_number"),
    )
    op.create_index("ix_order_items_etl_run_id", "order_items", ["etl_run_id"])
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    op.create_table(
        "data_quality_results",
        sa.Column("data_quality_result_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "etl_run_id",
            sa.Uuid(),
            sa.ForeignKey("etl_runs.etl_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_order_ids", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_customer_ids", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_product_ids", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_dates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("negative_sales", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_quantities", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_discounts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_numeric_values", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unknown_regions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unreasonable_profit_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issue_counts", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("etl_run_id", name="uq_data_quality_results_etl_run_id"),
    )

    op.create_table(
        "rejected_records",
        sa.Column("rejected_record_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "etl_run_id",
            sa.Uuid(),
            sa.ForeignKey("etl_runs.etl_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("rejection_reasons", postgresql.JSONB(), nullable=False),
        sa.Column("original_record", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("source_row_number >= 2", name="ck_rejected_records_source_row_number"),
    )
    op.create_index("ix_rejected_records_etl_run_id", "rejected_records", ["etl_run_id"])


def downgrade() -> None:
    """Drop the schema in reverse dependency order."""
    op.drop_table("rejected_records")
    op.drop_table("data_quality_results")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("etl_runs")
    op.drop_table("products")
    op.drop_table("customers")
