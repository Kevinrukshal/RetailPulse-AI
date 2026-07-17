"""Unit tests for validation, rejection auditing, and quality reports."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from etl.exceptions import EmptyDatasetError, MissingRequiredColumnsError
from etl.mapping import CANONICAL_COLUMNS
from etl.quality_report import write_quality_outputs
from etl.validate import validate_sales_data

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def valid_row() -> dict[str, object]:
    """Return one independently mutable canonical row."""
    return pd.read_csv(FIXTURES / "valid_sales.csv").iloc[0].to_dict()


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"order_id": ""}, "missing_order_id"),
        ({"customer_id": "  "}, "missing_customer_id"),
        ({"product_id": None}, "missing_product_id"),
        ({"order_date": "not-a-date"}, "invalid_order_date"),
        ({"ship_date": "not-a-date"}, "invalid_ship_date"),
        (
            {"order_date": "2025-05-10", "ship_date": "2025-05-01"},
            "ship_date_before_order_date",
        ),
        ({"sales": "many"}, "invalid_sales"),
        ({"sales": -0.01}, "negative_sales"),
        ({"quantity": "several"}, "invalid_quantity"),
        ({"quantity": 0}, "nonpositive_quantity"),
        ({"discount": "none"}, "invalid_discount"),
        ({"discount": 1.01}, "discount_out_of_range"),
        ({"profit": "unknown"}, "invalid_profit"),
        ({"region": "North"}, "unknown_region"),
    ],
)
def test_rejects_each_critical_rule(updates: dict[str, object], reason: str) -> None:
    row = {**valid_row(), **updates}

    result = validate_sales_data(pd.DataFrame([row]))

    assert result.metrics.valid_rows == 0
    assert reason in result.rejected_rows.iloc[0]["rejection_reasons"]


def test_collects_all_reasons_and_does_not_mutate_input() -> None:
    data = pd.DataFrame(
        [{**valid_row(), "order_id": "", "sales": -10, "quantity": 0, "region": "Moon"}]
    )
    original = data.copy(deep=True)

    result = validate_sales_data(data)

    assert_frame_equal(data, original)
    assert set(result.rejected_rows.iloc[0]["rejection_reasons"]) >= {
        "missing_order_id",
        "negative_sales",
        "nonpositive_quantity",
        "unknown_region",
    }


def test_rejects_only_later_exact_duplicates() -> None:
    row = valid_row()

    result = validate_sales_data(pd.DataFrame([row, row]))

    assert result.metrics.valid_rows == 1
    assert result.metrics.duplicate_rows == 1
    assert result.rejected_rows.iloc[0]["rejection_reasons"] == ["duplicate_row"]


def test_quality_score_counts_each_rejected_row_once() -> None:
    good = valid_row()
    bad = {**valid_row(), "order_id": "", "sales": -1, "region": "Unknown"}

    result = validate_sales_data(pd.DataFrame([good, bad]))

    assert result.metrics.total_rows == 2
    assert result.metrics.invalid_rows == 1
    assert result.metrics.quality_score == 50.0


def test_unreasonable_profit_is_a_noncritical_warning() -> None:
    row = {**valid_row(), "sales": 100, "profit": 20_000}

    result = validate_sales_data(pd.DataFrame([row]))

    assert result.metrics.valid_rows == 1
    assert result.metrics.unreasonable_profit_rows == 1
    assert result.valid_rows.iloc[0]["validation_warnings"] == ["unreasonable_profit"]


def test_validates_intentional_invalid_fixture() -> None:
    data = pd.read_csv(FIXTURES / "invalid_sales.csv")

    result = validate_sales_data(data)

    assert result.metrics.total_rows == 12
    assert result.metrics.invalid_rows == 11
    assert result.rejected_rows["rejection_reasons"].map(bool).all()
    assert result.metrics.issue_counts["duplicate_row"] == 1


def test_rejects_dataset_missing_required_columns() -> None:
    with pytest.raises(MissingRequiredColumnsError, match="profit"):
        validate_sales_data(pd.DataFrame([{"order_id": "A-1"}]))


def test_rejects_empty_dataset() -> None:
    with pytest.raises(EmptyDatasetError, match="no rows"):
        validate_sales_data(pd.DataFrame(columns=CANONICAL_COLUMNS))


def test_writes_csv_json_and_markdown_quality_outputs(tmp_path: Path) -> None:
    data = pd.DataFrame([valid_row(), {**valid_row(), "order_id": ""}])
    result = validate_sales_data(data)
    run_id = UUID("12345678-1234-5678-1234-567812345678")
    timestamp = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)

    paths = write_quality_outputs(
        result,
        output_root=tmp_path,
        etl_run_id=run_id,
        source_file=Path("sample_sales.csv"),
        source_file_hash="abc123",
        started_at=timestamp,
        completed_at=timestamp,
    )

    assert all(path.exists() for path in paths.__dict__.values())
    report = json.loads(paths.json_report.read_text(encoding="utf-8"))
    assert report["etl_run_id"] == str(run_id)
    assert report["quality_score"] == 50.0
    assert "round(100 * valid_rows / total_rows, 2)" in paths.markdown_report.read_text(
        encoding="utf-8"
    )
    rejected = pd.read_csv(paths.rejected_rows)
    assert json.loads(rejected.iloc[0]["rejection_reasons"])
