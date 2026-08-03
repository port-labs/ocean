from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from datadog.client import (
    DATADOG_UNKNOWN_STATUS_CODE,
    DatadogClient,
    _create_datadog_retry_config,
)


def test_datadog_retry_config_includes_transient_status_codes() -> None:
    config = _create_datadog_retry_config()

    assert HTTPStatus.INTERNAL_SERVER_ERROR in config.retry_status_codes
    assert DATADOG_UNKNOWN_STATUS_CODE in config.retry_status_codes
    assert "X-RateLimit-Reset" in config.retry_after_headers
    assert HTTPStatus.INTERNAL_SERVER_ERROR in config.ignore_retry_after_status_codes
    assert DATADOG_UNKNOWN_STATUS_CODE in config.ignore_retry_after_status_codes


@pytest.mark.asyncio
async def test_send_api_request_logs_rate_limit_headers_on_429(
    mock_datadog_client: DatadogClient,
) -> None:
    rate_limit_response = httpx.Response(
        HTTPStatus.TOO_MANY_REQUESTS,
        request=httpx.Request("GET", "https://api.datadoghq.com/api/v1/monitor"),
        headers={
            "X-RateLimit-Remaining": "10",
            "X-RateLimit-Reset": "1710000000",
        },
    )

    with (
        patch.object(
            mock_datadog_client.http_client,
            "request",
            new_callable=AsyncMock,
            return_value=rate_limit_response,
        ),
        patch("datadog.client.logger") as mock_logger,
        pytest.raises(httpx.HTTPStatusError),
    ):
        mock_bound = MagicMock()
        mock_logger.bind.return_value = mock_bound

        await mock_datadog_client.send_api_request(
            "https://api.datadoghq.com/api/v1/monitor",
            params={"page": 556, "page_size": 100},
        )

    mock_logger.bind.assert_called_once_with(
        remaining="10",
        reset="1710000000",
        method="GET",
        url="https://api.datadoghq.com/api/v1/monitor",
    )
    mock_bound.warning.assert_called_once()
