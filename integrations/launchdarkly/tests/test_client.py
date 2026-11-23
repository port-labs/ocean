import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import httpx
from httpx import AsyncClient, HTTPStatusError
from typing import Any, Generator
from client import LaunchDarklyClient


@pytest.fixture
def mock_http_client() -> AsyncClient:
    """Create a mock HTTP client."""
    return AsyncMock(spec=AsyncClient)


@pytest.fixture
def mock_integration_config() -> Generator[dict[str, str], None, None]:
    """Mock the ocean integration config."""
    config = {
        "launchdarkly_host": "https://app.launchdarkly.com",
        "launchdarkly_token": "test_token",
        "webhook_secret": "test_secret",
    }
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.fixture
async def mock_client(
    mock_integration_config: dict[str, str], mock_http_client: AsyncClient
) -> LaunchDarklyClient:
    """Create LaunchDarklyClient using create_from_ocean_config."""
    return LaunchDarklyClient.create_from_ocean_configuration()


@pytest.mark.asyncio
async def test_send_api_request_success(mock_client: LaunchDarklyClient) -> None:
    """Test successful API request."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": "test"}
    with patch.object(
        mock_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        result = await mock_client.send_api_request("test/endpoint")
        assert result == {"data": "test"}
        mock_request.assert_called_once_with(
            method="GET",
            url=f"{mock_client.api_url}/test/endpoint",
            params=None,
            json=None,
        )


@pytest.mark.asyncio
async def test_send_api_request_with_params(mock_client: LaunchDarklyClient) -> None:
    """Test API request with query parameters."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": "test"}
    params = [("limit", "100")]
    with patch.object(
        mock_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        result = await mock_client.send_api_request(
            "test/endpoint", query_params=params
        )
        assert result == {"data": "test"}
        mock_request.assert_called_once_with(
            method="GET",
            url=f"{mock_client.api_url}/test/endpoint",
            params=params,
            json=None,
        )


@pytest.mark.asyncio
async def test_send_api_request_error(mock_client: LaunchDarklyClient) -> None:
    """Test API request with error response."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": "Test error message"}

    original_error = HTTPStatusError(
        "400 Client Error", request=MagicMock(), response=mock_response
    )
    mock_response.raise_for_status.side_effect = original_error

    with (
        patch.object(
            mock_client.http_client, "request", new_callable=AsyncMock
        ) as mock_request,
        patch("client.logger.error") as mock_logger,
    ):
        mock_request.return_value = mock_response

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_client.send_api_request("test/endpoint")

        assert exc_info.value == original_error
        mock_logger.assert_called_once()


@pytest.mark.asyncio
async def test_get_paginated_resource(mock_client: LaunchDarklyClient) -> None:
    """Test paginated resource fetching."""
    page1 = {
        "items": [{"id": 1}, {"id": 2}],
        "_links": {"next": {"href": "/api/v2/test?page=2"}},
    }
    page2 = {"items": [{"id": 3}], "totalCount": 3}

    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page1, page2]
        batches = []
        async for batch in mock_client.get_paginated_resource("test"):
            batches.append(batch)

        assert batches[0] == [{"id": 1}, {"id": 2}]
        assert batches[1] == [{"id": 3}]
        assert len(batches) == 2

        all_results = [item for batch in batches for item in batch]
        assert len(all_results) == 3
        assert [item["id"] for item in all_results] == [1, 2, 3]


@pytest.mark.asyncio
async def test_get_feature_flag_status(mock_client: LaunchDarklyClient) -> None:
    """Test getting feature flag status."""
    mock_response = {
        "key": "test-flag",
        "environments": {"env1": {"on": True}, "env2": {"on": False}},
    }
    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        result = await mock_client.get_feature_flag_status("project-1", "test-flag")
        assert result == mock_response
        mock_request.assert_called_once_with("flag-status/project-1/test-flag")


@pytest.mark.asyncio
async def test_patch_webhook(mock_client: LaunchDarklyClient) -> None:
    """Test patching webhook with secret."""
    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        await mock_client.patch_webhook("webhook-1", "new-secret")
        mock_request.assert_called_once_with(
            endpoint="webhooks/webhook-1",
            method="PATCH",
            json_data=[{"op": "replace", "path": "/secret", "value": "new-secret"}],
        )


@pytest.mark.asyncio
async def test_create_launchdarkly_webhook_new(mock_client: LaunchDarklyClient) -> None:
    """Test creating a new webhook."""
    mock_response: dict[str, list[Any]] = {"items": []}
    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        await mock_client.create_launchdarkly_webhook("https://test.com")
        mock_request.assert_called_with(
            endpoint="webhooks",
            method="POST",
            json_data={
                "url": "https://test.com/integration/webhook",
                "description": "Port Integration Webhook",
                "sign": True,
                "secret": "test_secret",
            },
        )


@pytest.mark.asyncio
async def test_create_launchdarkly_webhook_existing(
    mock_client: LaunchDarklyClient,
) -> None:
    """Test handling existing webhook."""
    mock_response = {
        "items": [
            {
                "_id": "webhook-1",
                "url": "https://test.com/integration/webhook",
                "secret": None,
            }
        ]
    }
    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        await mock_client.create_launchdarkly_webhook("https://test.com")
        mock_request.assert_called_with(
            endpoint="webhooks/webhook-1",
            method="PATCH",
            json_data=[{"op": "replace", "path": "/secret", "value": "test_secret"}],
        )


@pytest.fixture
def flags_response() -> dict[str, Any]:
    return {
        "items": [{"key": "flag-1", "name": "Test Flag"}],
        "totalCount": 1,
    }


@pytest.mark.asyncio
async def test_fetch_feature_flags_default_selector(
    mock_client: LaunchDarklyClient, flags_response: dict[str, Any]
) -> None:
    """Test fetching feature flags with default selector (summary=true)."""
    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = flags_response

        result = await mock_client.fetch_feature_flags_for_project({"key": "project-1"})

        assert len(result) == 1
        assert result[0]["__projectKey"] == "project-1"
        params = mock_request.call_args[1]["query_params"]
        assert params == [("limit", "100")]


@pytest.mark.asyncio
async def test_fetch_feature_flags_with_environments(
    mock_client: LaunchDarklyClient, flags_response: dict[str, Any]
) -> None:
    """Test fetching feature flags with summary=false and environments."""
    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = flags_response

        result = await mock_client.fetch_feature_flags_for_project(
            {"key": "project-1"},
            summary=False,
            environments=["production", "staging"],
        )

        assert len(result) == 1
        params = mock_request.call_args[1]["query_params"]
        assert ("limit", "100") in params
        assert ("summary", "0") in params
        assert ("env", "production") in params
        assert ("env", "staging") in params


@pytest.mark.asyncio
async def test_get_feature_flag(mock_client: LaunchDarklyClient) -> None:
    """Test getting a single feature flag with environments."""
    flag_response = {"key": "flag-1", "name": "Test Flag"}

    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = flag_response

        result = await mock_client.get_feature_flag(
            "project-1", "flag-1", ["production", "staging"]
        )

        assert result["key"] == "flag-1"
        mock_request.assert_called_once_with(
            "flags/project-1/flag-1",
            query_params=[("env", "production"), ("env", "staging")],
        )


@pytest.mark.parametrize(
    "next_hrefs,selector_params",
    [
        # Default selector - no extra params
        (
            [
                "/api/v2/flags/project-1?offset=100",
                "/api/v2/flags/project-1?offset=200",
            ],
            [],
        ),
        # Configured selector with summary and env
        (
            [
                "/api/v2/flags/project-1?offset=100",
                "/api/v2/flags/project-1?offset=200",
            ],
            [("summary", "0"), ("env", "production")],
        ),
    ],
)
@pytest.mark.asyncio
async def test_pagination_preserves_params(
    mock_client: LaunchDarklyClient,
    next_hrefs: list[str],
    selector_params: list[tuple[str, str]],
) -> None:
    """Test that pagination preserves params without duplicating across 3 pages."""
    page1 = {"items": [{"key": "flag-1"}], "_links": {"next": {"href": next_hrefs[0]}}}
    page2 = {"items": [{"key": "flag-2"}], "_links": {"next": {"href": next_hrefs[1]}}}
    page3 = {"items": [{"key": "flag-3"}], "totalCount": 3}

    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page1, page2, page3]

        batches = []
        async for batch in mock_client.get_paginated_resource(
            "flag",
            resource_path="project-1",
            extra_params=selector_params if selector_params else None,
        ):
            batches.extend(batch)

        assert len(batches) == 3

        # Check page 2 URL params - build URL from actual href + params sent
        page2_call = mock_request.call_args_list[1]
        page2_endpoint = page2_call[1]["endpoint"]
        page2_params = page2_call[1]["query_params"]

        # Build URL to check final result - endpoint is the full href from LaunchDarkly
        # which includes offset, and params are the extra ones we add
        page2_url = httpx.URL(f"https://api.launchdarkly.com{page2_endpoint}")
        final_page2_params = dict(page2_url.params)
        for k, v in page2_params:
            if k not in final_page2_params:
                final_page2_params[k] = v

        # Each key should appear exactly once
        assert final_page2_params.get("offset") == "100"
        assert final_page2_params.get("limit") == "100"
        if selector_params:
            assert final_page2_params.get("summary") == "0"
            assert final_page2_params.get("env") == "production"
        else:
            assert "summary" not in final_page2_params
            assert "env" not in final_page2_params

        # Check page 3 URL params
        page3_call = mock_request.call_args_list[2]
        page3_endpoint = page3_call[1]["endpoint"]
        page3_params = page3_call[1]["query_params"]

        page3_url = httpx.URL(f"https://api.launchdarkly.com{page3_endpoint}")
        final_page3_params = dict(page3_url.params)
        for k, v in page3_params:
            if k not in final_page3_params:
                final_page3_params[k] = v

        # Each key should appear exactly once with new offset
        assert final_page3_params.get("offset") == "200"
        assert final_page3_params.get("limit") == "100"
        if selector_params:
            assert final_page3_params.get("summary") == "0"
            assert final_page3_params.get("env") == "production"
        else:
            assert "summary" not in final_page3_params
            assert "env" not in final_page3_params
