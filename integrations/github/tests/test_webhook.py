import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    return FastAPI()


@pytest.fixture(autouse=True)
def mock_ocean(app):
    mock_ocean = MagicMock()
    mock_ocean.on_start = lambda: lambda x: x
    mock_ocean.on_resync = lambda x=None: lambda y: y
    mock_ocean.router = app.router
    mock_ocean.create_http_client = lambda: AsyncMock()
    mock_ocean.fast_api_app = app

    with patch("port_ocean.context.ocean.ocean", mock_ocean):
        yield mock_ocean


def test_webhook_issues_event(app, mock_ocean):
    from main import github_webhook  # noqa: F401 — ensures route gets registered

    client = TestClient(app)

    payload = {
        "action": "opened",
        "issue": {"title": "Bug: Fix crash"},
        "repository": {"full_name": "kunmi02/ocean"}
    }
    headers = {"x-github-event": "issues"}

    response = client.post("/webhook", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json()["ok"] is True
