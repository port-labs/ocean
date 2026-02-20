import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from clients.github_client import GitHubClient
from tests.mocks import (
    organizations_response,
    copilot_usage_report_manifest,
    copilot_usage_report_part_1,
    copilot_usage_report_part_2,
)


BASE_URL = "https://api.github.com"
TOKEN = "test-token"


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "github_token": TOKEN,
            "github_host": BASE_URL,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def github_client() -> GitHubClient:
    return GitHubClient(base_url=BASE_URL, token=TOKEN)


@pytest.mark.asyncio
async def test_get_organizations_single_page(github_client: GitHubClient) -> None:
    expected_response = organizations_response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = expected_response
    mock_response.headers = {}

    with patch.object(
        github_client._client, "request", new=AsyncMock(return_value=mock_response)
    ):
        results = []
        async for orgs in github_client.get_organizations():
            results.extend(orgs)

        assert results == expected_response


@pytest.mark.asyncio
async def test_get_metrics_for_organization_fetches_and_combines_all_report_parts(
    github_client: GitHubClient,
) -> None:
    manifest_response = MagicMock()
    manifest_response.status_code = 200
    manifest_response.json.return_value = copilot_usage_report_manifest

    signed_url_response_part_1 = MagicMock()
    signed_url_response_part_1.status_code = 200
    signed_url_response_part_1.json.return_value = copilot_usage_report_part_1

    signed_url_response_part_2 = MagicMock()
    signed_url_response_part_2.status_code = 200
    signed_url_response_part_2.json.return_value = copilot_usage_report_part_2

    request_mock = AsyncMock(
        side_effect=[
            manifest_response,
            signed_url_response_part_1,
            signed_url_response_part_2,
        ]
    )

    with patch.object(github_client._client, "request", new=request_mock):
        result = await github_client.get_metrics_for_organization(
            organizations_response[0]
        )

    assert result == copilot_usage_report_part_1 + copilot_usage_report_part_2


@pytest.mark.asyncio
async def test_get_metrics_for_organization_returns_none_when_forbidden(
    github_client: GitHubClient,
) -> None:
    forbidden_response = httpx.Response(
        status_code=403, request=httpx.Request("GET", BASE_URL)
    )
    request_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Forbidden",
            request=forbidden_response.request,
            response=forbidden_response,
        )
    )

    with patch.object(github_client._client, "request", new=request_mock):
        result = await github_client.get_metrics_for_organization(
            organizations_response[0]
        )

    assert result is None


@pytest.mark.asyncio
async def test_get_metrics_for_organization_returns_none_when_manifest_has_no_download_links(
    github_client: GitHubClient,
) -> None:
    empty_manifest_response = MagicMock()
    empty_manifest_response.status_code = 200
    empty_manifest_response.json.return_value = {
        "download_links": [],
        "report_start_day": "2025-07-01",
        "report_end_day": "2025-07-28",
    }

    with patch.object(
        github_client._client,
        "request",
        new=AsyncMock(return_value=empty_manifest_response),
    ):
        result = await github_client.get_metrics_for_organization(
            organizations_response[0]
        )

    assert result is None


@pytest.mark.asyncio
async def test_fetch_report_from_signed_url_returns_parsed_report_data(
    github_client: GitHubClient,
) -> None:
    signed_url = "https://signed.example.com/copilot-report-part-1.json"
    expected_report_data = copilot_usage_report_part_1

    signed_url_response = MagicMock()
    signed_url_response.status_code = 200
    signed_url_response.json.return_value = expected_report_data

    with patch.object(
        github_client._client,
        "request",
        new=AsyncMock(return_value=signed_url_response),
    ):
        result = await github_client._fetch_report_from_signed_url(signed_url)

    assert result == expected_report_data


@pytest.mark.asyncio
async def test_fetch_report_from_signed_url_raises_on_http_error(
    github_client: GitHubClient,
) -> None:
    signed_url = "https://signed.example.com/copilot-report-expired.json"

    expired_url_response = httpx.Response(
        status_code=403, request=httpx.Request("GET", signed_url)
    )
    request_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Forbidden",
            request=expired_url_response.request,
            response=expired_url_response,
        )
    )

    with patch.object(github_client._client, "request", new=request_mock):
        with pytest.raises(httpx.HTTPStatusError):
            await github_client._fetch_report_from_signed_url(signed_url)


@pytest.mark.asyncio
async def test_paginated_response(github_client: GitHubClient) -> None:
    first_response = MagicMock()
    first_response.status_code = 200
    first_response.json.return_value = [{"item": 1}]
    first_response.headers = {"Link": f'<{BASE_URL}/paginated?page=2>; rel="next"'}

    second_response = MagicMock()
    second_response.status_code = 200
    second_response.json.return_value = [{"item": 2}]
    second_response.headers = {}

    async_mock = AsyncMock(side_effect=[first_response, second_response])

    with patch.object(github_client, "_send_api_request", new=async_mock):
        results = []
        async for page in github_client._get_paginated_data("paginated"):
            results.extend(page)

        assert results == [{"item": 1}, {"item": 2}]


@pytest.mark.asyncio
async def test_send_api_request_404_returns_empty(github_client: GitHubClient) -> None:
    error_response = httpx.Response(
        status_code=404, request=httpx.Request("get", "https://fake")
    )
    async_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Not Found", request=error_response.request, response=error_response
        )
    )

    with patch.object(github_client._client, "request", new=async_mock):
        result = await github_client.send_api_request("get", "not-found")
        assert result == []


def test_resolve_route_params() -> None:
    endpoint = "/orgs/{org}/teams/{team}/metrics"
    params = {"org": "acme", "team": "devs"}
    result = GitHubClient._resolve_route_params(endpoint, params)
    assert result == "/orgs/acme/teams/devs/metrics"
