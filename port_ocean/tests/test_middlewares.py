from unittest.mock import MagicMock, patch

import pytest

from port_ocean import middlewares


@pytest.mark.parametrize(
    "initialized,route_prefix,expected_prefix",
    [
        (False, "", "/health/"),
        (True, "", "/health/"),
        (True, "/my-prefix", "/my-prefix/health/"),
        (True, "/foo/health/bar", "/foo/health/bar/health/"),
    ],
)
def test_health_debug_path_prefix_matches_ocean_mount(
    initialized: bool, route_prefix: str, expected_prefix: str
) -> None:
    mock_ocean = MagicMock()
    mock_ocean.initialized = initialized
    mock_app = MagicMock()
    mock_app.route_prefix = route_prefix
    mock_ocean.app = mock_app

    with patch.object(middlewares, "ocean", mock_ocean):
        assert (
            middlewares._health_request_path_prefix_for_debug_logs() == expected_prefix
        )


def test_integration_path_under_prefix_with_health_segment_not_treated_as_health() -> (
    None
):
    """Regression: ``path_prefix`` may contain ``health``; only ``…/health/…`` mount is DEBUG."""
    mock_ocean = MagicMock()
    mock_ocean.initialized = True
    mock_app = MagicMock()
    mock_app.route_prefix = "/foo/health/bar"
    mock_ocean.app = mock_app

    with patch.object(middlewares, "ocean", mock_ocean):
        prefix = middlewares._health_request_path_prefix_for_debug_logs()

    integration_path = "/foo/health/bar/integration/webhook"
    health_path = "/foo/health/bar/health/live"

    assert not integration_path.startswith(prefix)
    assert health_path.startswith(prefix)
