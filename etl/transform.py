"""Deterministic transformations for validated retail order-line records."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import pandas as pd

from etl.mapping import CANONICAL_COLUMNS, normalize_column_name

TEXT_COLUMNS = (
    "order_id",
    "customer_id",
    "customer_name",
    "segment",
    "country",
    "city",
    "state",
    "region",
    "product_id",
    "product_name",
    "category",
    "subcategory",
)
NUMERIC_COLUMNS = ("sales", "quantity", "discount", "profit")
REGION_NAMES = {"central": "Central", "east": "East", "south": "South", "west": "West"}
CATEGORY_NAMES = {
    "furniture": "Furniture",
    "office supplies": "Office Supplies",
    "technology": "Technology",
}
SEGMENT_NAMES = {
    "consumer": "Consumer",
    "corporate": "Corporate",
    "home office": "Home Office",
}


def transform_sales_data(
    data: pd.DataFrame,
    *,
    etl_run_id: UUID,
    source_file_hash: str,
    loaded_at: datetime,
) -> pd.DataFrame:
    """Return a transformed copy of validated rows ready for relational loading."""
    result = data.copy(deep=True)
    result.columns = [normalize_column_name(column) for column in result.columns]
    duplicate_columns = result.columns[result.columns.duplicated()].tolist()
    if duplicate_columns:
        raise ValueError(f"Columns are ambiguous after normalization: {duplicate_columns}")

    required = set(CANONICAL_COLUMNS) | {"source_row_number"}
    missing = sorted(required - set(result.columns))
    if missing:
        raise ValueError(f"Validated data is missing transformation fields: {', '.join(missing)}")
    if not source_file_hash.strip():
        raise ValueError("source_file_hash must not be empty")

    result = result.drop_duplicates(subset=list(CANONICAL_COLUMNS), keep="first").reset_index(
        drop=True
    )
    for column in TEXT_COLUMNS:
        result[column] = result[column].astype("string").str.strip()

    result["category"] = _canonical_text(result["category"], CATEGORY_NAMES)
    result["subcategory"] = result["subcategory"].str.title()
    result["segment"] = _canonical_text(result["segment"], SEGMENT_NAMES)
    result["region"] = _canonical_text(result["region"], REGION_NAMES)

    result["order_date"] = pd.to_datetime(result["order_date"], errors="raise")
    result["ship_date"] = pd.to_datetime(result["ship_date"], errors="raise")
    for column in NUMERIC_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="raise")
    result["quantity"] = result["quantity"].astype("int64")

    result["year"] = result["order_date"].dt.year.astype("int64")
    result["month"] = result["order_date"].dt.month.astype("int64")
    result["month_name"] = result["order_date"].dt.month_name()
    result["quarter"] = "Q" + result["order_date"].dt.quarter.astype("string")
    result["year_month"] = result["order_date"].dt.strftime("%Y-%m")

    result["profit_margin"] = result["profit"].div(result["sales"].where(result["sales"].ne(0)))
    result["profit_margin"] = result["profit_margin"].round(6)
    result["revenue_per_unit"] = result["sales"].div(
        result["quantity"].where(result["quantity"].ne(0))
    )
    result["revenue_per_unit"] = result["revenue_per_unit"].round(2)
    result["discount_band"] = result["discount"].map(_discount_band)
    result["profit_status"] = result["profit"].map(_profit_status)

    normalized_loaded_at = (
        loaded_at.replace(tzinfo=UTC) if loaded_at.tzinfo is None else loaded_at.astimezone(UTC)
    )
    normalized_hash = source_file_hash.strip().lower()
    result["etl_run_id"] = str(etl_run_id)
    result["source_file_hash"] = normalized_hash
    result["loaded_at"] = normalized_loaded_at
    result["order_item_key"] = result.apply(
        lambda row: build_order_item_key(
            source_file_hash=normalized_hash,
            order_id=str(row["order_id"]),
            product_id=str(row["product_id"]),
            source_row_number=int(row["source_row_number"]),
        ),
        axis=1,
    )
    return result


def build_order_item_key(
    *,
    source_file_hash: str,
    order_id: str,
    product_id: str,
    source_row_number: int,
) -> str:
    """Build a stable line key while preserving repeated products in one order."""
    identity = "\x1f".join(
        (
            source_file_hash.strip().lower(),
            order_id.strip(),
            product_id.strip(),
            str(source_row_number),
        )
    )
    return sha256(identity.encode("utf-8")).hexdigest()


def _canonical_text(values: pd.Series, names: dict[str, str]) -> pd.Series:
    """Apply known canonical names and title-case otherwise."""
    normalized = values.str.casefold()
    return normalized.map(names).fillna(values.str.title())


def _discount_band(discount: float) -> str:
    """Classify a normalized discount ratio."""
    if discount == 0:
        return "None"
    if discount <= 0.10:
        return "Low"
    if discount <= 0.20:
        return "Medium"
    return "High"


def _profit_status(profit: float) -> str:
    """Classify a line by profitability."""
    if profit > 0:
        return "Profit"
    if profit < 0:
        return "Loss"
    return "Break-even"
