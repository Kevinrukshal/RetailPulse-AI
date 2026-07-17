"""Transactional, idempotent loading into the normalized PostgreSQL schema."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database.models import (
    Customer,
    DataQualityResult,
    EtlRun,
    Order,
    OrderItem,
    Product,
    RejectedRecord,
)
from etl.mapping import CANONICAL_COLUMNS
from etl.validate import ValidationResult


@dataclass(frozen=True)
class LoadSummary:
    """Counts returned after one successful database transaction."""

    customers_processed: int
    products_processed: int
    orders_processed: int
    order_items_inserted: int
    rejected_records_inserted: int


def create_etl_run(
    session: Session,
    *,
    etl_run_id: UUID,
    source_file: str,
    source_file_hash: str,
    started_at: datetime,
) -> None:
    """Persist a running audit record before data processing begins."""
    session.add(
        EtlRun(
            etl_run_id=etl_run_id,
            source_file=source_file,
            source_file_hash=source_file_hash,
            status="running",
            started_at=started_at,
            total_rows=0,
            valid_rows=0,
            invalid_rows=0,
        )
    )
    session.commit()


def mark_etl_run_failed(
    session: Session,
    *,
    etl_run_id: UUID,
    completed_at: datetime,
    duration_seconds: float,
    error_details: str,
) -> None:
    """Record a safe, bounded failure description in a separate transaction."""
    session.execute(
        update(EtlRun)
        .where(EtlRun.etl_run_id == etl_run_id)
        .values(
            status="failed",
            completed_at=completed_at,
            duration_seconds=Decimal(str(round(duration_seconds, 3))),
            error_details=error_details[:2000],
        )
    )
    session.commit()


def load_pipeline_results(
    session: Session,
    *,
    transformed_rows: pd.DataFrame,
    validation: ValidationResult,
    etl_run_id: UUID,
    started_at: datetime,
    completed_at: datetime,
) -> LoadSummary:
    """Load business and quality records; caller owns the transaction boundary."""
    customers = _customer_records(transformed_rows)
    products = _product_records(transformed_rows)
    orders = _order_records(transformed_rows)
    items = _order_item_records(transformed_rows, etl_run_id)

    if customers:
        statement = insert(Customer).values(customers)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Customer.customer_id],
                set_={
                    "customer_name": statement.excluded.customer_name,
                    "segment": statement.excluded.segment,
                    "country": statement.excluded.country,
                    "city": statement.excluded.city,
                    "state": statement.excluded.state,
                    "region": statement.excluded.region,
                    "updated_at": func.now(),
                },
            )
        )
    if products:
        statement = insert(Product).values(products)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Product.product_id],
                set_={
                    "product_name": statement.excluded.product_name,
                    "category": statement.excluded.category,
                    "subcategory": statement.excluded.subcategory,
                    "updated_at": func.now(),
                },
            )
        )
    if orders:
        statement = insert(Order).values(orders)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Order.order_id],
                set_={
                    "customer_id": statement.excluded.customer_id,
                    "order_date": statement.excluded.order_date,
                    "ship_date": statement.excluded.ship_date,
                    "updated_at": func.now(),
                },
            )
        )

    inserted_items = 0
    if items:
        inserted_keys = session.scalars(
            insert(OrderItem)
            .values(items)
            .on_conflict_do_nothing(index_elements=[OrderItem.order_item_key])
            .returning(OrderItem.order_item_key)
        ).all()
        inserted_items = len(inserted_keys)

    quality = validation.metrics
    session.add(
        DataQualityResult(
            etl_run_id=etl_run_id,
            duplicate_rows=quality.duplicate_rows,
            missing_order_ids=quality.missing_order_ids,
            missing_customer_ids=quality.missing_customer_ids,
            missing_product_ids=quality.missing_product_ids,
            invalid_dates=quality.invalid_dates,
            negative_sales=quality.negative_sales,
            invalid_quantities=quality.invalid_quantities,
            invalid_discounts=quality.invalid_discounts,
            invalid_numeric_values=quality.invalid_numeric_values,
            unknown_regions=quality.unknown_regions,
            unreasonable_profit_rows=quality.unreasonable_profit_rows,
            issue_counts=quality.issue_counts,
        )
    )

    rejected = _rejected_records(validation.rejected_rows, etl_run_id)
    if rejected:
        session.execute(insert(RejectedRecord).values(rejected))

    duration = Decimal(str(round((completed_at - started_at).total_seconds(), 3)))
    session.execute(
        update(EtlRun)
        .where(EtlRun.etl_run_id == etl_run_id)
        .values(
            status="completed",
            completed_at=completed_at,
            duration_seconds=duration,
            total_rows=quality.total_rows,
            valid_rows=quality.valid_rows,
            invalid_rows=quality.invalid_rows,
            quality_score=Decimal(str(quality.quality_score)),
            error_details=None,
        )
    )
    return LoadSummary(
        customers_processed=len(customers),
        products_processed=len(products),
        orders_processed=len(orders),
        order_items_inserted=inserted_items,
        rejected_records_inserted=len(rejected),
    )


def _customer_records(data: pd.DataFrame) -> list[dict[str, Any]]:
    columns = [
        "customer_id",
        "customer_name",
        "segment",
        "country",
        "city",
        "state",
        "region",
    ]
    return data[columns].drop_duplicates("customer_id", keep="last").to_dict(orient="records")


def _product_records(data: pd.DataFrame) -> list[dict[str, Any]]:
    columns = ["product_id", "product_name", "category", "subcategory"]
    return data[columns].drop_duplicates("product_id", keep="last").to_dict(orient="records")


def _order_records(data: pd.DataFrame) -> list[dict[str, Any]]:
    columns = ["order_id", "customer_id", "order_date", "ship_date"]
    records = data[columns].drop_duplicates("order_id", keep="last").to_dict(orient="records")
    for record in records:
        record["order_date"] = _date_value(record["order_date"])
        record["ship_date"] = _date_value(record["ship_date"])
    return records


def _order_item_records(data: pd.DataFrame, etl_run_id: UUID) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in data.to_dict(orient="records"):
        records.append(
            {
                "order_item_key": row["order_item_key"],
                "order_id": row["order_id"],
                "product_id": row["product_id"],
                "etl_run_id": etl_run_id,
                "source_file_hash": row["source_file_hash"],
                "source_row_number": int(row["source_row_number"]),
                "sales": Decimal(str(row["sales"])),
                "quantity": int(row["quantity"]),
                "discount": Decimal(str(row["discount"])),
                "profit": Decimal(str(row["profit"])),
                "loaded_at": row["loaded_at"],
            }
        )
    return records


def _rejected_records(data: pd.DataFrame, etl_run_id: UUID) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in data.to_dict(orient="records"):
        records.append(
            {
                "etl_run_id": etl_run_id,
                "source_row_number": int(row["source_row_number"]),
                "rejection_reasons": list(row["rejection_reasons"]),
                "original_record": {
                    column: _json_safe(row[column]) for column in CANONICAL_COLUMNS
                },
            }
        )
    return records


def _date_value(value: Any) -> date:
    """Convert Pandas and Python date-like values to a plain date."""
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _json_safe(value: Any) -> Any:
    """Convert Pandas and numeric scalars to PostgreSQL JSON-compatible values."""
    if value is None:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    try:
        if pd.isna(value):
            return None
    except TypeError, ValueError:
        pass
    return value
