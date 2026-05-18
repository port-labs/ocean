"""Tests for the path-scoped bearer-auth middleware."""

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aws.webhook.middleware import (
    _extract_bearer_token,
    build_live_events_auth_middleware,
)


LIVE_EVENTS_PATH = "/integration/webhook/live-events"
SECRET = "shhh-very-secret"


def _build_app(integration_config: Dict[str, Any]) -> FastAPI:
    """Build a FastAPI app with the middleware mounted and a stub handler."""
    app = FastAPI()

    middleware = build_live_events_auth_middleware(LIVE_EVENTS_PATH)
    app.middleware("http")(middleware)

    @app.post(LIVE_EVENTS_PATH)
    async def receive_event() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/integration/other-endpoint")
    async def other_endpoint() -> Dict[str, str]:
        return {"status": "ok"}

    app.dependency_overrides = {}

    mock_ocean = MagicMock()
    mock_ocean.integration_config = integration_config

    # Patch the symbol the middleware closure resolves at request time.
    app.state._mock_ocean = mock_ocean
    return app


class TestExtractBearerToken:
    def test_returns_token_with_bearer_prefix(self) -> None:
        assert _extract_bearer_token("Bearer hunter2") == "hunter2"

    def test_returns_token_case_insensitive_prefix(self) -> None:
        assert _extract_bearer_token("bearer hunter2") == "hunter2"

    def test_returns_none_for_missing_header(self) -> None:
        assert _extract_bearer_token(None) is None

    def test_returns_none_for_other_scheme(self) -> None:
        assert _extract_bearer_token("Basic dXNlcjpwYXNz") is None

    def test_returns_none_for_empty_token(self) -> None:
        assert _extract_bearer_token("Bearer ") is None


class TestLiveEventsAuthMiddleware:
    @pytest.fixture
    def app(self) -> FastAPI:
        return _build_app({"webhook_secret": SECRET})

    @pytest.fixture
    def app_without_secret(self) -> FastAPI:
        return _build_app({})

    def test_rejects_missing_bearer_with_401(self, app: FastAPI) -> None:
        with patch("aws.webhook.middleware.ocean", app.state._mock_ocean):
            client = TestClient(app)
            response = client.post(LIVE_EVENTS_PATH, json={})

        assert response.status_code == 401

    def test_rejects_wrong_bearer_with_401(self, app: FastAPI) -> None:
        with patch("aws.webhook.middleware.ocean", app.state._mock_ocean):
            client = TestClient(app)
            response = client.post(
                LIVE_EVENTS_PATH,
                json={},
                headers={"Authorization": "Bearer wrong"},
            )

        assert response.status_code == 401

    def test_wrong_bearer_logs_safe_diagnostics(self, app: FastAPI) -> None:
        with patch("aws.webhook.middleware.ocean", app.state._mock_ocean):
            with patch(
                "aws.webhook.middleware._log_live_events_auth_rejection"
            ) as log_rej:
                client = TestClient(app)
                client.post(
                    LIVE_EVENTS_PATH,
                    json={},
                    headers={"Authorization": "Bearer wrong-token"},
                )
        log_rej.assert_called_once()
        kwargs = log_rej.call_args.kwargs
        assert kwargs["reason_code"] == "bearer_token_mismatch"
        assert kwargs["provided_token"] == "wrong-token"
        assert kwargs["configured_secret"] == SECRET

    def test_rejects_non_bearer_scheme_with_401(self, app: FastAPI) -> None:
        with patch("aws.webhook.middleware.ocean", app.state._mock_ocean):
            client = TestClient(app)
            response = client.post(
                LIVE_EVENTS_PATH,
                json={},
                headers={"Authorization": "Basic dXNlcjpwYXNz"},
            )

        assert response.status_code == 401

    def test_rejects_when_secret_not_configured(
        self, app_without_secret: FastAPI
    ) -> None:
        with patch(
            "aws.webhook.middleware.ocean", app_without_secret.state._mock_ocean
        ):
            client = TestClient(app_without_secret)
            response = client.post(
                LIVE_EVENTS_PATH,
                json={},
                headers={"Authorization": f"Bearer {SECRET}"},
            )

        assert response.status_code == 401

    def test_accepts_correct_bearer_with_200(self, app: FastAPI) -> None:
        with patch("aws.webhook.middleware.ocean", app.state._mock_ocean):
            client = TestClient(app)
            response = client.post(
                LIVE_EVENTS_PATH,
                json={},
                headers={"Authorization": f"Bearer {SECRET}"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_does_not_touch_other_endpoints(self, app: FastAPI) -> None:
        with patch("aws.webhook.middleware.ocean", app.state._mock_ocean):
            client = TestClient(app)
            response = client.post("/integration/other-endpoint", json={})

        assert response.status_code == 200

    def test_does_not_touch_get_requests(self, app: FastAPI) -> None:
        @app.get(LIVE_EVENTS_PATH)
        async def receive_get() -> Dict[str, str]:
            return {"status": "ok"}

        with patch("aws.webhook.middleware.ocean", app.state._mock_ocean):
            client = TestClient(app)
            response = client.get(LIVE_EVENTS_PATH)

        assert response.status_code == 200
