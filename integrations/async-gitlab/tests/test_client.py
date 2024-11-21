import pytest
import httpx
from unittest.mock import AsyncMock
from gitlab.helpers.utils import ObjectKind
from gitlab.gitlab_client import GitLabClient

@pytest.fixture
def gitlab_client():
    return GitLabClient(gitlab_host="https://gitlab.example.com", access_token="dummy_token")

@pytest.mark.asyncio
async def test_api_auth_header(gitlab_client):
    assert gitlab_client.api_auth_header == {"Authorization": "Bearer dummy_token"}

@pytest.mark.asyncio
async def test_send_api_request_success(gitlab_client, mocker):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.json.return_value = {"key": "value"}
    mock_response.status_code = 200
    mocker.patch.object(
        gitlab_client.http_client,
        "request",
        return_value=mock_response,
    )

    response = await gitlab_client.send_api_request(endpoint="test/endpoint")
    assert response.json() == {"key": "value"}

@pytest.mark.asyncio
async def test_send_api_request_http_error(gitlab_client, mocker):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Error", request=AsyncMock(), response=mock_response
    )
    mocker.patch.object(
        gitlab_client.http_client,
        "request",
        return_value=mock_response,
    )

    with pytest.raises(httpx.HTTPStatusError):
        await gitlab_client.send_api_request(endpoint="test/endpoint")

@pytest.mark.asyncio
async def test_get_paginated_resources(gitlab_client, mocker):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.json.side_effect = [[{"id": 1}], [{"id": 2}]]
    mock_response.headers = {"x-next-page": None}
    mock_response.raise_for_status.return_value = None

    mocker.patch.object(
        gitlab_client,
        "send_api_request",
        side_effect=[mock_response, mock_response],
    )

    resource_type = ObjectKind.PROJECT
    results = []
    async for page in gitlab_client.get_paginated_resources(resource_type):
        results.extend(page)

    assert results == [{"id": 1}, {"id": 2}]

@pytest.mark.asyncio
async def test_create_resource(gitlab_client, mocker):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.json.return_value = {"id": 1, "name": "test"}
    mock_response.status_code = 201

    mocker.patch.object(
        gitlab_client,
        "send_api_request",
        return_value=mock_response,
    )

    payload = {"name": "test"}
    response = await gitlab_client.create_resource(path="projects", payload=payload)
    assert response == {"id": 1, "name": "test"}

@pytest.mark.asyncio
async def test_create_from_ocean_config(mocker):
    mock_event = mocker.patch("port_ocean.context.event")
    mock_event.attributes.get.return_value = None

    mock_ocean = mocker.patch("port_ocean.context.ocean")
    mock_ocean.integration_config = {
        "gitlab_host": "https://gitlab.example.com",
        "access_token": "dummy_token",
    }

    gitlab_client = GitLabClient.create_from_ocean_config()
    assert isinstance(gitlab_client, GitLabClient)
    assert gitlab_client.base_url == "https://gitlab.example.com/api/v4"
