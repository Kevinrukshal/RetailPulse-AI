"""Unit tests for deterministic sales transformations."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from etl.transform import build_order_item_key, transform_sales_data
from etl.validate import validate_sales_data

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
RUN_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
SOURCE_HASH = "1" * 64
LOADED_AT = datetime(2026, 7, 17, 15, 30, tzinfo=UTC)


def validated_row(**updates: object) -> pd.DataFrame:
    """Return one valid audited row with optional field changes."""
    row = pd.read_csv(FIXTURES / "valid_sales.csv").iloc[0].to_dict()
    row.update(updates)
    return validate_sales_data(pd.DataFrame([row])).valid_rows


def transform(data: pd.DataFrame) -> pd.DataFrame:
    """Transform using stable test metadata."""
    return transform_sales_data(
        data,
        etl_run_id=RUN_ID,
        source_file_hash=SOURCE_HASH,
        loaded_at=LOADED_AT,
    )


def test_derives_calendar_financial_and_audit_fields_without_mutation() -> None:
    data = validated_row(
        order_date="2025-05-15",
        ship_date="2025-05-18",
        sales=100,
        quantity=4,
        discount=0.10,
        profit=25,
    )
    original = data.copy(deep=True)

    result = transform(data)

    assert_frame_equal(data, original)
    row = result.iloc[0]
    assert (row["year"], row["month"], row["month_name"]) == (2025, 5, "May")
    assert (row["quarter"], row["year_month"]) == ("Q2", "2025-05")
    assert row["profit_margin"] == 0.25
    assert row["revenue_per_unit"] == 25.0
    assert (row["discount_band"], row["profit_status"]) == ("Low", "Profit")
    assert row["etl_run_id"] == str(RUN_ID)
    assert row["source_file_hash"] == SOURCE_HASH
    assert row["loaded_at"] == LOADED_AT


def test_normalizes_headers_and_business_text() -> None:
    data = validated_row(
        customer_name="  Demo Customer  ",
        category="office supplies",
        subcategory="  PAPER  ",
        segment="home office",
        region="west",
    ).rename(columns={"order_id": "Order ID"})

    row = transform(data).iloc[0]

    assert row["order_id"].startswith("RP-")
    assert row["customer_name"] == "Demo Customer"
    assert (row["category"], row["subcategory"]) == ("Office Supplies", "Paper")
    assert (row["segment"], row["region"]) == ("Home Office", "West")


@pytest.mark.parametrize(
    ("discount", "profit", "expected_band", "expected_status"),
    [
        (0, 0, "None", "Break-even"),
        (0.05, 1, "Low", "Profit"),
        (0.15, -1, "Medium", "Loss"),
        (0.30, -1, "High", "Loss"),
    ],
)
def test_classifies_discount_and_profit(
    discount: float,
    profit: float,
    expected_band: str,
    expected_status: str,
) -> None:
    row = transform(validated_row(discount=discount, profit=profit)).iloc[0]

    assert row["discount_band"] == expected_band
    assert row["profit_status"] == expected_status


def test_avoids_division_by_zero() -> None:
    row = transform(validated_row(sales=0, quantity=2, profit=0)).iloc[0]

    assert pd.isna(row["profit_margin"])
    assert row["revenue_per_unit"] == 0


def test_removes_defensive_exact_duplicates() -> None:
    data = validated_row()
    duplicate = pd.concat([data, data], ignore_index=True)
    duplicate.loc[1, "source_row_number"] = 99

    result = transform(duplicate)

    assert len(result) == 1


def test_order_item_key_is_stable_and_sensitive_to_identity() -> None:
    values = {
        "source_file_hash": SOURCE_HASH,
        "order_id": "O-1",
        "product_id": "P-1",
        "source_row_number": 2,
    }

    first = build_order_item_key(**values)
    second = build_order_item_key(**values)
    changed = build_order_item_key(**{**values, "source_row_number": 3})

    assert first == second
    assert first != changed
    assert len(first) == 64


def test_requires_validated_source_identity() -> None:
    data = validated_row().drop(columns="source_row_number")

    with pytest.raises(ValueError, match="source_row_number"):
        transform(data)
