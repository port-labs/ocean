import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
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
    params = {"limit": 100}
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


@pytest.mark.asyncio
async def test_get_paginated_resource_default_params_unchanged(
    mock_client: LaunchDarklyClient,
) -> None:
    """Without query_params the first request only carries the page size."""
    page1 = {
        "items": [{"id": 1}],
        "_links": {"next": {"href": "/api/v2/flags/proj?offset=1"}},
    }
    page2 = {"items": [{"id": 2}]}

    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page1, page2]
        batches = [batch async for batch in mock_client.get_paginated_resource("flag")]

    assert len(batches) == 2
    first_call, next_call = mock_request.call_args_list
    assert first_call.kwargs == {"endpoint": "flags", "query_params": {"limit": 100}}
    # Following a next link sends no params: the link already carries them.
    assert next_call.kwargs["query_params"] is None


@pytest.mark.asyncio
async def test_get_paginated_resource_merges_query_params(
    mock_client: LaunchDarklyClient,
) -> None:
    """Extra query params are sent on the first request only."""
    page1 = {
        "items": [{"id": 1}],
        "_links": {"next": {"href": "/api/v2/flags/proj?offset=1&summary=0"}},
    }
    page2 = {"items": [{"id": 2}]}

    with patch.object(
        mock_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page1, page2]
        _ = [
            batch
            async for batch in mock_client.get_paginated_resource(
                "flag",
                resource_path="proj",
                query_params={"summary": 0, "env": ["a", "b"]},
            )
        ]

    first_call, next_call = mock_request.call_args_list
    assert first_call.kwargs["endpoint"] == "flags/proj"
    assert first_call.kwargs["query_params"] == {
        "limit": 100,
        "summary": 0,
        "env": ["a", "b"],
    }
    assert next_call.kwargs["query_params"] is None


def test_environment_params_are_sent_as_repeated_env_parameters() -> None:
    """A list value is encoded as env=a&env=b, which is what LaunchDarkly expects."""
    params = httpx.QueryParams({"limit": 100, "summary": 0, "env": ["a", "b"]})
    assert str(params) == "limit=100&summary=0&env=a&env=b"


@pytest.mark.asyncio
async def test_fetch_feature_flags_default_skips_environments(
    mock_client: LaunchDarklyClient,
) -> None:
    """By default the environments are not listed and flags are requested as before."""
    with (
        patch.object(
            mock_client, "fetch_environments_for_project", new_callable=AsyncMock
        ) as mock_environments,
        patch.object(
            mock_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.return_value = {"items": [{"key": "flag-1"}]}
        flags = await mock_client.fetch_feature_flags_for_project({"key": "proj"})

    mock_environments.assert_not_awaited()
    mock_request.assert_awaited_once_with(
        endpoint="flags/proj", query_params={"limit": 100}
    )
    assert flags == [{"key": "flag-1", "__projectKey": "proj"}]


@pytest.mark.asyncio
async def test_fetch_feature_flags_with_environment_config(
    mock_client: LaunchDarklyClient,
) -> None:
    """With the option on, every environment of the project is requested."""
    with (
        patch.object(
            mock_client,
            "fetch_environments_for_project",
            new_callable=AsyncMock,
            return_value=[{"key": "production"}, {"key": "test"}],
        ) as mock_environments,
        patch.object(
            mock_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.return_value = {
            "items": [{"key": "flag-1", "environments": {"production": {"on": True}}}]
        }
        flags = await mock_client.fetch_feature_flags_for_project(
            {"key": "proj"}, include_environment_config=True
        )

    mock_environments.assert_awaited_once_with({"key": "proj"})
    mock_request.assert_awaited_once_with(
        endpoint="flags/proj",
        query_params={"limit": 100, "summary": 0, "env": ["production", "test"]},
    )
    assert flags[0]["__projectKey"] == "proj"
    assert flags[0]["environments"] == {"production": {"on": True}}


@pytest.mark.asyncio
async def test_fetch_feature_flags_with_environment_config_no_environments(
    mock_client: LaunchDarklyClient,
) -> None:
    """A project without environments falls back to the default request."""
    with (
        patch.object(
            mock_client,
            "fetch_environments_for_project",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch.object(
            mock_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request,
        patch("client.logger.warning") as mock_warning,
    ):
        mock_request.return_value = {"items": []}
        await mock_client.fetch_feature_flags_for_project(
            {"key": "proj"}, include_environment_config=True
        )

    mock_request.assert_awaited_once_with(
        endpoint="flags/proj", query_params={"limit": 100}
    )
    mock_warning.assert_called_once()


@pytest.mark.asyncio
async def test_get_paginated_feature_flags_propagates_environment_option(
    mock_client: LaunchDarklyClient,
) -> None:
    """The option reaches the per-project fetch for every project."""

    async def fake_projects() -> Any:
        yield [{"key": "p1"}, {"key": "p2"}]

    with (
        patch.object(mock_client, "get_paginated_projects", fake_projects),
        patch.object(
            mock_client,
            "fetch_feature_flags_for_project",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_fetch,
    ):
        _ = [
            batch
            async for batch in mock_client.get_paginated_feature_flags(
                include_environment_config=True
            )
        ]

    assert mock_fetch.await_count == 2
    for call in mock_fetch.await_args_list:
        assert call.kwargs == {"include_environment_config": True}
