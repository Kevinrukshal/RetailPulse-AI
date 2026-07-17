"""PostgreSQL integration tests for loading, idempotency, and rollback."""

import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import etl.pipeline as pipeline_module
from app.database.session import get_engine
from etl.pipeline import run_pipeline

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 with migrated PostgreSQL",
    ),
]

SAMPLE_FILE = Path("/app/data/sample/sample_sales.csv")
INVALID_FILE = Path("/app/tests/fixtures/invalid_sales.csv")


@pytest.fixture(autouse=True)
def clean_database() -> None:
    """Isolate each pipeline scenario while preserving the migrated schema."""
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "TRUNCATE rejected_records, data_quality_results, order_items, orders, "
                "products, customers, etl_runs RESTART IDENTITY CASCADE"
            )
        )


def table_count(table_name: str) -> int:
    """Return a count from a test-controlled table name."""
    allowed = {
        "customers",
        "products",
        "orders",
        "order_items",
        "etl_runs",
        "data_quality_results",
        "rejected_records",
    }
    if table_name not in allowed:
        raise ValueError(f"Unexpected test table: {table_name}")
    with get_engine().connect() as connection:
        return connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()


def test_pipeline_loads_sample_and_reruns_idempotently(tmp_path: Path) -> None:
    first = run_pipeline(SAMPLE_FILE, output_root=tmp_path)
    second = run_pipeline(SAMPLE_FILE, output_root=tmp_path)

    assert (first.total_rows, first.valid_rows, first.invalid_rows) == (750, 750, 0)
    assert first.load.order_items_inserted == 750
    assert second.load.order_items_inserted == 0
    assert table_count("customers") == 79
    assert table_count("products") == 20
    assert table_count("orders") == 311
    assert table_count("order_items") == 750
    assert table_count("etl_runs") == 2
    assert table_count("data_quality_results") == 2
    assert all(path.exists() for path in first.outputs.__dict__.values())


def test_pipeline_stores_every_rejected_record(tmp_path: Path) -> None:
    result = run_pipeline(INVALID_FILE, output_root=tmp_path)

    assert (result.total_rows, result.valid_rows, result.invalid_rows) == (12, 1, 11)
    assert result.load.rejected_records_inserted == 11
    assert table_count("rejected_records") == 11
    with get_engine().connect() as connection:
        assert connection.execute(
            text("SELECT bool_and(jsonb_array_length(rejection_reasons) > 0) FROM rejected_records")
        ).scalar_one()


def test_database_error_rolls_back_business_rows_and_marks_run_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_transform = pipeline_module.transform_sales_data

    def invalid_transform(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        transformed = original_transform(*args, **kwargs)
        transformed.loc[0, "quantity"] = 0
        return transformed

    monkeypatch.setattr(pipeline_module, "transform_sales_data", invalid_transform)

    with pytest.raises(IntegrityError):
        run_pipeline(SAMPLE_FILE, output_root=tmp_path)

    assert table_count("customers") == 0
    assert table_count("products") == 0
    assert table_count("orders") == 0
    assert table_count("order_items") == 0
    with get_engine().connect() as connection:
        status = connection.execute(text("SELECT status FROM etl_runs")).scalar_one()
    assert status == "failed"
