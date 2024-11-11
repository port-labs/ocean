import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import HTTPStatusError, Response
from typing import Any
from gitlab.helpers.utils import ObjectKind
from gitlab.client import GitLabClient


@pytest.fixture
def gitlab_client():
    return GitLabClient("https://gitlab.com", "fake_access_token")


@pytest.fixture
def mock_response():
    mock_resp = MagicMock(spec=Response)
    mock_resp.json.return_value = {"id": 1, "name": "test"}
    mock_resp.headers = {}
    return mock_resp


@patch("port_ocean.context.event.event.attributes", {})
@patch("port_ocean.context.ocean.integration_config",
       {"gitlab_host": "https://gitlab.com", "access_token": "fake_access_token"})
def test_create_from_ocean_config():
    client = GitLabClient.create_from_ocean_config()
    assert isinstance(client, GitLabClient)
    assert client.api_url == "https://gitlab.com/api"
    assert client.token == "fake_access_token"


@pytest.mark.asyncio
async def test_get_resource_api_version(gitlab_client):
    version = await gitlab_client.get_resource_api_version(ObjectKind.PROJECT)
    assert version == "v4"


@pytest.mark.asyncio
async def test_get_single_resource_success(gitlab_client, mock_response):
    with patch.object(gitlab_client.http_client, "get", return_value=mock_response) as mock_get:
        response = await gitlab_client._get_single_resource("https://gitlab.com/api/v4/projects/1")
        assert response.json() == {"id": 1, "name": "test"}
        mock_get.assert_called_once_with(url="https://gitlab.com/api/v4/projects/1", params=None)


@pytest.mark.asyncio
async def test_get_single_resource_http_error(gitlab_client):
    mock_response = MagicMock(spec=Response)
    mock_response.raise_for_status.side_effect = HTTPStatusError("Not Found", request=None, response=mock_response)
    with patch.object(gitlab_client.http_client, "get", return_value=mock_response):
        with pytest.raises(HTTPStatusError):
            await gitlab_client._get_single_resource("https://gitlab.com/api/v4/projects/1")


@pytest.mark.asyncio
async def test_get_paginated_resources_success(gitlab_client, mock_response):
    mock_response.json.return_value = [{"id": 1, "name": "test_project"}]
    with patch.object(gitlab_client, "_get_single_resource", return_value=mock_response) as mock_get:
        resource_generator = gitlab_client.get_paginated_resources(ObjectKind.PROJECT)
        resources = [resource async for resource in resource_generator]
        assert resources == [[{"id": 1, "name": "test_project"}]]
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_get_paginated_resources_pagination(gitlab_client):
    first_page_response = MagicMock(spec=Response)
    first_page_response.json.return_value = [{"id": 1, "name": "test_project"}]
    first_page_response.headers = {'x-next-page': '2',
                                   'link': '<https://gitlab.com/api/v4/projects?page=2>; rel="next"'}

    second_page_response = MagicMock(spec=Response)
    second_page_response.json.return_value = [{"id": 2, "name": "test_project_2"}]
    second_page_response.headers = {}

    with patch.object(gitlab_client, "_get_single_resource",
                      side_effect=[first_page_response, second_page_response]) as mock_get:
        resource_generator = gitlab_client.get_paginated_resources(ObjectKind.PROJECT)
        resources = [resource async for resource in resource_generator]
        assert resources == [[{"id": 1, "name": "test_project"}], [{"id": 2, "name": "test_project_2"}]]
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_get_resources_success(gitlab_client, mock_response):
    mock_response.json.return_value = [{"id": 1, "name": "test_project", "namespace": {"id": 100}}]
    with patch.object(gitlab_client, "get_paginated_resources", return_value=[mock_response]) as mock_paginated:
        resource_generator = gitlab_client.get_resources(ObjectKind.PROJECT)
        resources = [resource async for resource in resource_generator]

        assert resources == [[{"id": "1", "name": "test_project", "namespace": {"id": "100"}}]]
        mock_paginated.assert_called_once()


@pytest.mark.asyncio
async def test_get_resources_handle_ids(gitlab_client, mock_response):
    mock_response.json.return_value = [{"id": 1, "project_id": 2}]
    with patch.object(gitlab_client, "get_paginated_resources", return_value=[mock_response]) as mock_paginated:
        resource_generator = gitlab_client.get_resources(ObjectKind.MERGE_REQUEST)
        resources = [resource async for resource in resource_generator]
        assert resources == [[{"id": "1", "project_id": "2"}]]
        mock_paginated.assert_called_once()
