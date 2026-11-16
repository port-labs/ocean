"""
Test that Plain probe does NOT retry on 401 (Unauthorized).

When test connection gets a 401 from Plain API, it should:
1. Make exactly ONE request (no retries)
2. Mark probe status as FAILED
3. Provide a clear message that credentials were rejected
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from http import HTTPStatus
import httpx

from plain.probe.probe import PlainPermissionProbe
from port_ocean.core.probe import ProbeContext, ProbeStatus


@pytest.mark.asyncio
async def test_probe_401_makes_exactly_one_request_no_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    REGRESSION TEST: When Plain API returns 401, probe should make exactly
    ONE request and NOT retry it ~10 times.

    Root cause: PlainClient.execute() sets extensions={"retryable": True},
    causing RetryTransport to retry 401s by default.

    This test uses the REAL OceanAsyncClient with RetryTransport to verify
    the actual retry behavior.
    """
    # Track request count through the real transport stack
    request_count = {"count": 0}

    # Mock the innermost HTTP transport to track requests
    class CountingTransport(httpx.AsyncHTTPTransport):
        async def handle_async_request(self, request):
            request_count["count"] += 1
            # Always return 401
            return httpx.Response(
                HTTPStatus.UNAUTHORIZED,
                request=request,
                content=b'{"errors":[{"message":"Unauthorized"}]}',
            )

    monkeypatch.setattr("httpx.AsyncHTTPTransport", CountingTransport)

    # Mock ocean config
    mock_ocean = Mock()
    mock_ocean.integration_config = {
        "api_token": "test-token",
        "api_url": "https://core-api.uk.plain.com/graphql/v1",
    }
    mock_ocean.config.client_timeout = 30
    mock_ocean.config.integration.identifier = "plain-test"
    mock_ocean.config.ssl.third_party.enabled = False
    mock_ocean.config.ssl.third_party.certificate = None
    mock_ocean.config.disable_ip_outbound_blocker = True
    monkeypatch.setattr("plain.client.ocean", mock_ocean)
    monkeypatch.setattr("port_ocean.helpers.async_client.ocean", mock_ocean)

    # Patch asyncio.sleep to speed up retries (though there shouldn't be any)
    with patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()):
        # Run the probe
        context = ProbeContext()
        context.reporter = Mock()
        context.reporter.report = AsyncMock()
        context.available_kinds = ["company"]

        await PlainPermissionProbe(context).run()

    # Assert: Should make MORE than ONE request because 401 is being retried
    # This test SHOULD FAIL initially, proving the bug exists
    assert request_count["count"] == 1, (
        f"Expected exactly 1 request, but got {request_count['count']}. "
        "This means 401 is being retried when it shouldn't be."
    )

    # Assert: Probe should be marked as FAILED
    assert context.status is ProbeStatus.FAILED

    # Assert: Message should indicate authentication failure
    assert context.message is not None
    assert any(
        keyword in context.message.lower()
        for keyword in ["authentication", "credentials", "unauthorized", "401"]
    ), f"Expected clear auth failure message, got: {context.message}"


@pytest.mark.asyncio
async def test_resync_calls_still_retry_on_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify that normal resync/webhook calls (skip_retry=False) STILL get retried.
    Only probe/test-connection calls should skip retries.
    """
    request_count = {"count": 0}

    # Mock the innermost HTTP transport to track requests
    class CountingTransport(httpx.AsyncHTTPTransport):
        async def handle_async_request(self, request):
            request_count["count"] += 1
            if request_count["count"] < 3:
                # First 2 attempts: return 503 (retryable)
                return httpx.Response(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    request=request,
                    content=b'{"errors":[{"message":"Service unavailable"}]}',
                )
            else:
                # Third attempt: success with proper GraphQL response
                import json

                return httpx.Response(
                    HTTPStatus.OK,
                    request=request,
                    content=json.dumps(
                        {"data": {"myPermissions": {"permissions": ["company:read"]}}}
                    ).encode(),
                    headers={"content-type": "application/json"},
                )

    monkeypatch.setattr("httpx.AsyncHTTPTransport", CountingTransport)

    # Mock ocean config
    mock_ocean = Mock()
    mock_ocean.integration_config = {
        "api_token": "test-token",
        "api_url": "https://core-api.uk.plain.com/graphql/v1",
    }
    mock_ocean.config.client_timeout = 30
    mock_ocean.config.integration.identifier = "plain-test"
    mock_ocean.config.ssl.third_party.enabled = False
    mock_ocean.config.ssl.third_party.certificate = None
    mock_ocean.config.disable_ip_outbound_blocker = True
    monkeypatch.setattr("plain.client.ocean", mock_ocean)
    monkeypatch.setattr("port_ocean.helpers.async_client.ocean", mock_ocean)

    # Patch asyncio.sleep to speed up retries
    with patch("port_ocean.helpers.retry.asyncio.sleep", new=AsyncMock()):
        from plain.client import PlainClient

        client = PlainClient()
        # Call without skip_retry (normal resync behavior)
        try:
            result = await client.get_my_permissions(skip_retry=False)
        except Exception as e:
            pytest.fail(
                f"Expected retries to succeed after 3 attempts, but got exception: {e}. "
                f"Request count: {request_count['count']}"
            )

    # Should have retried (3 attempts total)
    assert (
        request_count["count"] == 3
    ), f"Expected 3 requests (2 retries), got {request_count['count']}"

    # Should succeed after retries
    assert result == {"company:read": True}


@pytest.mark.asyncio
async def test_probe_status_is_failed_not_internal_failure_on_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify that 401 during probe marks status as FAILED (third-party failure),
    not INTERNAL_FAILURE (our bug).
    """

    # Mock the innermost HTTP transport
    class Http401Transport(httpx.AsyncHTTPTransport):
        async def handle_async_request(self, request):
            return httpx.Response(
                HTTPStatus.UNAUTHORIZED,
                request=request,
                content=b'{"errors":[{"message":"Unauthorized"}]}',
            )

    monkeypatch.setattr("httpx.AsyncHTTPTransport", Http401Transport)

    # Mock ocean config
    mock_ocean = Mock()
    mock_ocean.integration_config = {
        "api_token": "test-token",
        "api_url": "https://core-api.uk.plain.com/graphql/v1",
    }
    mock_ocean.config.client_timeout = 30
    mock_ocean.config.integration.identifier = "plain-test"
    mock_ocean.config.ssl.third_party.enabled = False
    mock_ocean.config.ssl.third_party.certificate = None
    mock_ocean.config.disable_ip_outbound_blocker = True
    monkeypatch.setattr("plain.client.ocean", mock_ocean)
    monkeypatch.setattr("port_ocean.helpers.async_client.ocean", mock_ocean)

    # Run the probe
    context = ProbeContext()
    context.reporter = Mock()
    context.reporter.report = AsyncMock()
    context.available_kinds = ["company"]

    await PlainPermissionProbe(context).run()

    # Assert: Should be FAILED, not INTERNAL_FAILURE
    assert context.status is ProbeStatus.FAILED
    assert context.status is not ProbeStatus.INTERNAL_FAILURE

    # Message should mention authentication/credentials
    assert context.message is not None
    assert "authentication" in context.message.lower() or "401" in context.message
