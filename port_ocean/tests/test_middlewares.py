from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from port_ocean import middlewares
from port_ocean.middlewares import request_handler


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,expected_level,route_prefix,initialized",
    [
        ("/docs", "DEBUG", "", True),
        ("/openapi.json", "DEBUG", "", True),
        ("/health/live", "DEBUG", "", True),
        ("/health/ready", "DEBUG", "", True),
        ("/my-prefix/health/live", "DEBUG", "/my-prefix", True),
        ("/my-prefix/health/ready", "DEBUG", "/my-prefix", True),
        ("/integration/x", "INFO", "", True),
        ("/foo/health/bar/health/live", "DEBUG", "/foo/health/bar", True),
        ("/foo/health/bar/health/ready", "DEBUG", "/foo/health/bar", True),
        ("/foo/health/bar/integration/x", "INFO", "/foo/health/bar", True),
        ("/health/live", "DEBUG", "", False),
    ],
)
async def test_request_handler_log_level(
    path: str,
    expected_level: str,
    route_prefix: str,
    initialized: bool,
) -> None:
    request = MagicMock(spec=Request)
    request.url.path = path
    request.method = "GET"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {}

    mock_bind = MagicMock()

    mock_ocean = MagicMock()
    mock_ocean.initialized = initialized
    mock_app = MagicMock()
    mock_app.route_prefix = route_prefix
    mock_ocean.app = mock_app

    with patch("port_ocean.middlewares.logger") as mock_logger:
        mock_logger.bind.return_value = mock_bind
        with patch.object(middlewares, "ocean", mock_ocean):
            with patch(
                "port_ocean.middlewares._handle_silently",
                new=AsyncMock(return_value=mock_response),
            ):
                await request_handler(request, AsyncMock())

    levels = [c.args[0] for c in mock_bind.log.call_args_list if c.args]
    assert levels == [expected_level, expected_level]
