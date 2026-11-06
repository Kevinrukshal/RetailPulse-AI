"""Integration tests for read-only analytics API contracts."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api import security
from app.api.dependencies import get_read_only_session
from app.core.config import Settings
from app.database.session import get_engine
from app.main import app
from etl.pipeline import run_pipeline

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 with migrated PostgreSQL",
    ),
]


@pytest.fixture(scope="module", autouse=True)
def loaded_api_sample(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Load one clean sample for API contract tests."""
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "TRUNCATE rejected_records, data_quality_results, order_items, orders, "
                "products, customers, etl_runs RESTART IDENTITY CASCADE"
            )
        )
    run_pipeline(
        Path("/app/data/sample/sample_sales.csv"),
        output_root=tmp_path_factory.mktemp("api"),
    )


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: Settings(api_access_token="test-token-" + "x" * 32, _env_file=None),
    )
    with TestClient(
        app,
        raise_server_exceptions=False,
        headers={"Authorization": "Bearer test-token-" + "x" * 32},
    ) as test_client:
        yield test_client


def test_health_and_executive_summary(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}

    response = client.get("/api/v1/summary")

    assert response.status_code == 200
    assert response.json()["total_orders"] == 311
    assert isinstance(response.json()["total_revenue"], float)


def test_filters_and_query_validation(client: TestClient) -> None:
    filtered = client.get(
        "/api/v1/summary",
        params={"start_date": "2025-01-01", "region": "West", "category": "Technology"},
    )
    invalid_dates = client.get(
        "/api/v1/summary",
        params={"start_date": "2025-12-31", "end_date": "2025-01-01"},
    )
    invalid_sort = client.get("/api/v1/products/top", params={"sort_by": "drop table"})

    assert filtered.status_code == 200
    assert 0 <= filtered.json()["total_orders"] < 311
    assert invalid_dates.status_code == 422
    assert invalid_sort.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/revenue/monthly",
        "/api/v1/products/top?limit=5&sort_by=profit",
        "/api/v1/products/loss-making",
        "/api/v1/customers/top?limit=5",
        "/api/v1/customers/segments",
        "/api/v1/regions/performance",
        "/api/v1/profit-leakage?limit=5",
    ],
)
def test_analytics_collections_return_lists(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_quality_and_paginated_etl_history(client: TestClient) -> None:
    quality = client.get("/api/v1/data-quality/latest")
    runs = client.get("/api/v1/etl-runs", params={"limit": 1, "offset": 0})

    assert quality.status_code == 200
    assert quality.json()["quality_score"] == 100.0
    assert runs.status_code == 200
    assert runs.json()["total"] == 1
    assert len(runs.json()["items"]) == 1


def test_upload_processes_a_real_csv(client: TestClient) -> None:
    source = Path("/app/tests/fixtures/valid_sales.csv")

    response = client.post(
        "/api/v1/upload",
        params={"filename": source.name},
        content=source.read_bytes(),
        headers={"content-type": "application/octet-stream"},
    )

    assert response.status_code == 201
    assert response.json()["filename"] == "valid_sales.csv"
    assert response.json()["valid_rows"] == response.json()["total_rows"]
    assert response.json()["invalid_rows"] == 0


def test_openapi_exposes_only_expected_operations() -> None:
    assert app.openapi()["info"]["version"] == "1.2.0"
    operations = {
        method
        for path in app.openapi()["paths"].values()
        for method in path
        if method in {"get", "post", "put", "patch", "delete"}
    }

    assert operations == {"get", "post"}
    post_paths = {path for path, methods in app.openapi()["paths"].items() if "post" in methods}
    assert post_paths == {"/api/v1/assistant/query", "/api/v1/upload"}


def test_database_errors_return_safe_503(client: TestClient) -> None:
    class BrokenSession:
        def execute(self, *_: object, **__: object) -> None:
            raise OperationalError("SELECT", {}, Exception("secret internal detail"))

        def rollback(self) -> None:
            return None

    def broken_dependency():  # type: ignore[no-untyped-def]
        yield BrokenSession()

    app.dependency_overrides[get_read_only_session] = broken_dependency
    try:
        response = client.get("/api/v1/summary")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Analytics database is unavailable"}
    assert "secret" not in response.text


def test_cors_preflight_uses_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/summary",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
