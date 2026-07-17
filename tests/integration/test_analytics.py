"""Integration tests for analytical views and documented SQL queries."""

import os
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from app.database.session import get_engine
from etl.pipeline import run_pipeline

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 with migrated PostgreSQL",
    ),
]

EXPECTED_VIEWS = {
    "executive_summary",
    "monthly_performance",
    "product_performance",
    "customer_performance",
    "regional_performance",
    "profit_leakage",
}


@pytest.fixture(scope="module", autouse=True)
def loaded_sample(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Load one isolated sample for all analytics assertions."""
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "TRUNCATE rejected_records, data_quality_results, order_items, orders, "
                "products, customers, etl_runs RESTART IDENTITY CASCADE"
            )
        )
    run_pipeline(
        Path("/app/data/sample/sample_sales.csv"),
        output_root=tmp_path_factory.mktemp("analytics"),
    )


def test_expected_analytics_views_exist() -> None:
    assert EXPECTED_VIEWS.issubset(inspect(get_engine()).get_view_names())


def test_executive_summary_matches_normalized_facts() -> None:
    with get_engine().connect() as connection:
        summary = connection.execute(text("SELECT * FROM executive_summary")).mappings().one()
        raw = (
            connection.execute(
                text(
                    "SELECT SUM(sales) AS revenue, SUM(profit) AS profit, "
                    "COUNT(DISTINCT order_id) AS orders FROM order_items"
                )
            )
            .mappings()
            .one()
        )

    assert summary["total_revenue"] == raw["revenue"]
    assert summary["total_profit"] == raw["profit"]
    assert summary["total_orders"] == raw["orders"] == 311


def test_ranked_and_leakage_views_return_data() -> None:
    with get_engine().connect() as connection:
        assert (
            connection.execute(text("SELECT COUNT(*) FROM product_performance")).scalar_one() == 20
        )
        assert (
            connection.execute(text("SELECT COUNT(*) FROM customer_performance")).scalar_one() == 79
        )
        assert (
            connection.execute(text("SELECT COUNT(*) FROM regional_performance")).scalar_one() == 4
        )
        assert connection.execute(text("SELECT COUNT(*) FROM profit_leakage")).scalar_one() > 0


def test_all_documented_queries_execute() -> None:
    query_path = Path("/app/sql/analysis_queries.sql")
    sections = query_path.read_text(encoding="utf-8").split("-- query:")[1:]

    assert len(sections) >= 15
    with get_engine().connect() as connection:
        for section in sections:
            name, query = section.split("\n", 1)
            result = connection.execute(text(query.strip()))
            assert result.returns_rows, name.strip()
