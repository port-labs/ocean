from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock
from port_ocean.helpers.metric.metric import Metrics


def test_metrics_endpoints() -> None:
    """Test that both /metrics and /metrics/ endpoints work correctly."""
    # Create mock settings
    metrics_settings = Mock()
    metrics_settings.enabled = True

    integration_settings = Mock()
    integration_settings.type = "test"
    integration_settings.identifier = "test-integration"

    port_client = Mock()

    # Create metrics instance
    metrics = Metrics(
        metrics_settings=metrics_settings,
        integration_configuration=integration_settings,
        port_client=port_client,
        multiprocessing_enabled=False,
    )

    # Create FastAPI app with the metrics router using the same pattern as Ocean
    app = FastAPI()
    app.include_router(metrics.create_mertic_router(), prefix="/metrics")

    # Create test client
    client = TestClient(app)

    # Test both endpoints
    response_no_slash = client.get("/metrics")
    response_with_slash = client.get("/metrics/")

    # Both should return 200
    assert (
        response_no_slash.status_code == 200
    ), f"Expected 200, got {response_no_slash.status_code}"
    assert (
        response_with_slash.status_code == 200
    ), f"Expected 200, got {response_with_slash.status_code}"

    # Both should return the same content
    assert (
        response_no_slash.text == response_with_slash.text
    ), "Endpoints should return identical content"

    # Verify content type is text/plain (prometheus format)
    assert response_no_slash.headers["content-type"] == "text/plain; charset=utf-8"
    assert response_with_slash.headers["content-type"] == "text/plain; charset=utf-8"
