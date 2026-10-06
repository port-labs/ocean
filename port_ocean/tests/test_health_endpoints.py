from fastapi import FastAPI
from fastapi.testclient import TestClient

from port_ocean.health import create_health_router, set_ready


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

        set_ready(False)
        ready_not_started = client.get("/health/ready")
        assert ready_not_started.status_code == 503
        not_ready_body = ready_not_started.json()
        assert not_ready_body["status"] == "not_ready"
        assert not_ready_body["check"] == "ready"

        set_ready(True)
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        ready_body = ready.json()
        assert ready_body["status"] == "healthy"
        assert ready_body["check"] == "ready"
        assert isinstance(ready_body["core_version"], str)
