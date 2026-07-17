"""PostgreSQL integration tests for the Alembic-managed schema."""

import os

import pytest
from sqlalchemy import inspect, text

from app.database.session import get_engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 with migrated PostgreSQL",
    ),
]

EXPECTED_TABLES = {
    "customers",
    "products",
    "orders",
    "order_items",
    "etl_runs",
    "data_quality_results",
    "rejected_records",
}


def test_migration_creates_expected_tables() -> None:
    inspector = inspect(get_engine())

    assert EXPECTED_TABLES.issubset(inspector.get_table_names())


def test_order_items_has_stable_unique_key_and_foreign_keys() -> None:
    inspector = inspect(get_engine())

    unique_names = {item["name"] for item in inspector.get_unique_constraints("order_items")}
    foreign_tables = {item["referred_table"] for item in inspector.get_foreign_keys("order_items")}
    check_names = {item["name"] for item in inspector.get_check_constraints("order_items")}

    assert "uq_order_items_order_item_key" in unique_names
    assert foreign_tables == {"orders", "products", "etl_runs"}
    assert {
        "ck_order_items_sales",
        "ck_order_items_quantity",
        "ck_order_items_discount",
    }.issubset(check_names)


def test_database_connection_executes_query() -> None:
    with get_engine().connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
