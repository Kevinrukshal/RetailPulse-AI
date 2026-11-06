"""Unit coverage for the bounded browser upload workflow."""

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import security
from app.api.routes import upload
from app.core.config import Settings
from app.main import app


@pytest.fixture
def client(monkeypatch) -> TestClient:

    monkeypatch.setattr(
        upload, "get_settings", lambda: Settings(upload_enabled=True, _env_file=None)
    )
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


def test_dashboard_assets_are_served(client: TestClient) -> None:
    root = client.get("/", follow_redirects=False)
    page = client.get("/app/")
    script = client.get("/app/app.js")

    assert root.status_code in {307, 308}
    assert root.headers["location"] == "/app/"
    assert page.status_code == 200
    assert "RetailPulse AI" in page.text
    assert script.status_code == 200


def test_upload_runs_pipeline_and_removes_temporary_file(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: dict[str, object] = {}

    def fake_pipeline(path: Path) -> SimpleNamespace:
        observed["path"] = path
        observed["content"] = path.read_bytes()
        return SimpleNamespace(
            etl_run_id=uuid4(),
            total_rows=2,
            valid_rows=2,
            invalid_rows=0,
            quality_score=100.0,
            load=SimpleNamespace(order_items_inserted=2),
        )

    monkeypatch.setattr(upload, "UPLOAD_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(upload, "run_pipeline", fake_pipeline)
    response = client.post(
        "/api/v1/upload",
        params={"filename": "sales.csv"},
        content=b"Order ID,Sales\nA-1,42\n",
        headers={"content-type": "application/octet-stream"},
    )

    assert response.status_code == 201
    assert response.json()["order_items_inserted"] == 2
    assert observed["content"] == b"Order ID,Sales\nA-1,42\n"
    assert not Path(observed["path"]).exists()  # type: ignore[arg-type]
    assert list((tmp_path / "uploads").iterdir()) == []


@pytest.mark.parametrize(
    ("filename", "expected_status"),
    [("notes.txt", 415), ("../sales.csv", 422), (r"folder\sales.xlsx", 422)],
)
def test_upload_rejects_bad_names(client: TestClient, filename: str, expected_status: int) -> None:
    response = client.post("/api/v1/upload", params={"filename": filename}, content=b"not used")
    assert response.status_code == expected_status


def test_upload_rejects_empty_and_oversized_files(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(upload, "UPLOAD_ROOT", tmp_path / "uploads")
    empty = client.post("/api/v1/upload", params={"filename": "empty.csv"}, content=b"")

    monkeypatch.setattr(
        upload,
        "get_settings",
        lambda: SimpleNamespace(upload_enabled=True, upload_max_bytes=3, upload_max_mb=0.000003),
    )
    oversized = client.post("/api/v1/upload", params={"filename": "large.csv"}, content=b"1234")

    assert empty.status_code == 422
    assert oversized.status_code == 413


def test_upload_can_be_disabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(upload, "get_settings", lambda: SimpleNamespace(upload_enabled=False))
    response = client.post("/api/v1/upload", params={"filename": "sales.csv"}, content=b"data")
    assert response.status_code == 503
