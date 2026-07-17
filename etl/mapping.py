"""Configurable source-column mapping for canonical retail fields."""

import re
from collections.abc import Mapping

import pandas as pd

from etl.exceptions import ColumnMappingError

CANONICAL_COLUMNS: tuple[str, ...] = (
    "order_id",
    "order_date",
    "ship_date",
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
    "sales",
    "quantity",
    "discount",
    "profit",
)


def normalize_column_name(value: object) -> str:
    """Convert a source header to a stable snake_case lookup key."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip()).strip("_").lower()
    return re.sub(r"_+", "_", normalized)


def apply_column_mapping(
    data: pd.DataFrame,
    column_mapping: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Return a copy with normalized headers and optional source-to-canonical aliases."""
    aliases = {
        normalize_column_name(source): normalize_column_name(target)
        for source, target in (column_mapping or {}).items()
    }
    invalid_targets = sorted(set(aliases.values()) - set(CANONICAL_COLUMNS))
    if invalid_targets:
        raise ColumnMappingError(
            f"Column mapping targets are not canonical fields: {', '.join(invalid_targets)}"
        )

    mapped_columns = [
        aliases.get(normalize_column_name(column), normalize_column_name(column))
        for column in data.columns
    ]
    duplicates = sorted({name for name in mapped_columns if mapped_columns.count(name) > 1})
    if duplicates:
        raise ColumnMappingError(
            f"Multiple source columns map to the same field: {', '.join(duplicates)}"
        )

    result = data.copy()
    result.columns = mapped_columns
    return result
