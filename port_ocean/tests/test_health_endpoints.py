from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from port_ocean.health import create_health_router
from port_ocean.ocean import Ocean


def test_health_endpoints_return_json_payload() -> None:
    app = FastAPI()
    app.include_router(create_health_router(), prefix="/health")
    with TestClient(app) as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.headers["content-type"].startswith("application/json")
        live_body = live.json()
        assert live_body["status"] == "healthy"
        assert live_body["check"] == "live"
        assert isinstance(live_body["core_version"], str)
        assert live_body["core_version"]

        ready = client.get("/health/ready")
        assert ready.status_code == 200
        ready_body = ready.json()
        assert ready_body["status"] == "healthy"
        assert ready_body["check"] == "ready"
        assert isinstance(ready_body["core_version"], str)


def test_initialize_app_registers_health_routes() -> None:
    with patch("port_ocean.ocean.Ocean.__init__", return_value=None):
        ocean = Ocean()

    ocean.config = MagicMock()
    ocean.config.path_prefix = None
    ocean.fast_api_app = FastAPI()
    ocean.integration_router = MagicMock()
    ocean.metrics = MagicMock()
    ocean.metrics.create_mertic_router.return_value = MagicMock()

    ocean.initialize_app()

    paths = {
        route.path for route in ocean.fast_api_app.routes if isinstance(route, APIRoute)
    }
    assert "/health/live" in paths
    assert "/health/ready" in paths
