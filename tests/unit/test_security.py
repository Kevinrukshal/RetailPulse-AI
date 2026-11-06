"""Security boundaries must hold before database or provider access."""

import json
import sys
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient

from ai.provider import OpenAINarrator
from ai.query_router import AnalyticsIntent
from app.api import security
from app.core.config import Settings
from app.main import app
from etl import extract
from etl.exceptions import UnreadableDataFileError

TOKEN = "test-only-token-" + "x" * 32


@pytest.mark.parametrize(
    "path,method",
    [("/api/v1/summary", "get"), ("/api/v1/upload", "post"), ("/api/v1/assistant/query", "post")],
)
def test_missing_and_wrong_auth_never_reach_data(monkeypatch, path, method):
    monkeypatch.setattr(
        security, "get_settings", lambda: Settings(api_access_token=TOKEN, _env_file=None)
    )
    with TestClient(app) as client:
        assert getattr(client, method)(path).status_code == 401
        assert (
            getattr(client, method)(path, headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )


def test_auth_fails_closed_and_accepts_valid_token(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr(security, "get_settings", lambda: Settings(_env_file=None))
        assert client.get("/api/v1/assistant/status").status_code == 503
        monkeypatch.setattr(
            security, "get_settings", lambda: Settings(api_access_token=TOKEN, _env_file=None)
        )
        assert (
            client.get(
                "/api/v1/assistant/status", headers={"Authorization": f"Bearer {TOKEN}"}
            ).status_code
            == 200
        )


def test_csv_row_limit_rejects_instead_of_truncating(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "MAX_ROWS", 2)
    path = tmp_path / "rows.csv"
    path.write_text("a\n1\n2\n3\n")
    with pytest.raises(UnreadableDataFileError, match="row limit"):
        extract.extract_sales_data(path)


def test_expanded_archive_limit_checked_before_excel_parser(tmp_path, monkeypatch):
    monkeypatch.setattr(extract, "MAX_EXPANDED_BYTES", 100)
    path = tmp_path / "large.xlsx"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("sheet.xml", "x" * 101)
    with pytest.raises(UnreadableDataFileError, match="expanded archive"):
        extract.extract_sales_data(path)


def test_provider_excludes_customer_identifiers_and_free_text(monkeypatch):
    captured = {}

    class Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_text="Summary")

    monkeypatch.setitem(
        sys.modules,
        "openai",
        SimpleNamespace(OpenAI=lambda **kwargs: SimpleNamespace(responses=Responses())),
    )
    OpenAINarrator(api_key="test", model="test").explain(
        question="private question",
        intent=AnalyticsIntent.TOP_CUSTOMERS,
        data=[{"customer_name": "Private Name", "customer_id": "secret-id", "lifetime_profit": 10}],
        context=[],
    )
    payload = captured["input"]
    assert "Private Name" not in payload and "secret-id" not in payload
    assert "private question" not in payload
    assert json.loads(payload)["query_result"][0]["lifetime_profit"] == 10


def test_rate_limit_is_bounded_and_recovers(monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request

    security._request_windows.clear()
    monkeypatch.setattr(security.time, "monotonic", lambda: 10.0)
    request = Request({"type": "http", "client": ("test-source", 1)})
    for _ in range(120):
        security.enforce_rate_limit(request)
    with pytest.raises(HTTPException) as exc:
        security.enforce_rate_limit(request)
    assert exc.value.status_code == 429
    monkeypatch.setattr(security.time, "monotonic", lambda: 71.0)
    security.enforce_rate_limit(request)
    security._request_windows.clear()


@pytest.mark.parametrize("body", [b"{broken", b"x" * 20000])
def test_unauthorized_json_denied_before_parsing(monkeypatch, body):
    monkeypatch.setattr(
        security, "get_settings", lambda: Settings(api_access_token=TOKEN, _env_file=None)
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assistant/query",
            content=body,
            headers={"Content-Type": "application/json", "Authorization": "Bearer wrong"},
        )
    assert response.status_code == 401


def test_authenticated_chunked_json_body_limit(monkeypatch):
    monkeypatch.setattr(
        security, "get_settings", lambda: Settings(api_access_token=TOKEN, _env_file=None)
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/assistant/query",
            content=iter([b"x" * 9000, b"y" * 9000]),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 413
