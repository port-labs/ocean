import pytest
import base64
from unittest.mock import patch, MagicMock, AsyncMock
from github_cloud.clients.rest_client import RestClient

@pytest.fixture
def rest_client():
    return RestClient("https://api.githubtest.com", "test_token")

@pytest.mark.asyncio
async def test_get_paginated_resource(rest_client):
    mock_response1 = MagicMock()
    mock_response1.status_code = 200
    mock_response1.json.return_value = [{"id": 1}, {"id": 2}]
    mock_response1.headers = {
        "Link": '<https://api.githubtest.com/page2>; rel="next"'
    }

    mock_response2 = MagicMock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = []
    mock_response2.headers = {}

    with patch.object(rest_client, "_client") as mock_client:
        mock_client.request.side_effect = [mock_response1, mock_response2]
        batches = []
        async for batch in rest_client.get_paginated_resource("test/resource"):
            batches.append(batch)
            if len(batches) >= 2:
                break

        assert len(batches) == 1
        assert len(batches[0]) == 2
        assert batches[0][0]["id"] == 1
        assert batches[0][1]["id"] == 2

@pytest.mark.asyncio
async def test_get_paginated_org_resource(rest_client):
    mock_response1 = MagicMock()
    mock_response1.status_code = 200
    mock_response1.json.return_value = [{"id": 1}, {"id": 2}]
    mock_response1.headers = {
        "Link": '<https://api.githubtest.com/page2>; rel="next"'
    }

    mock_response2 = MagicMock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = []
    mock_response2.headers = {}

    with patch.object(rest_client, "_client") as mock_client:
        mock_client.request.side_effect = [mock_response1, mock_response2]
        batches = []
        async for batch in rest_client.get_paginated_org_resource("test-org", "teams"):
            batches.append(batch)
            if len(batches) >= 2:
                break

        assert len(batches) == 1
        assert len(batches[0]) == 2
        assert batches[0][0]["id"] == 1
        assert batches[0][1]["id"] == 2

@pytest.mark.asyncio
async def test_get_paginated_repo_resource(rest_client):
    mock_response1 = MagicMock()
    mock_response1.status_code = 200
    mock_response1.json.return_value = [{"id": 1}, {"id": 2}]
    mock_response1.headers = {
        "Link": '<https://api.githubtest.com/page2>; rel="next"'
    }

    mock_response2 = MagicMock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = []
    mock_response2.headers = {}

    with patch.object(rest_client, "_client") as mock_client:
        mock_client.request.side_effect = [mock_response1, mock_response2]
        batches = []
        async for batch in rest_client.get_paginated_repo_resource("owner/repo", "issues"):
            batches.append(batch)
            if len(batches) >= 2:
                break

        assert len(batches) == 1
        assert len(batches[0]) == 2
        assert batches[0][0]["id"] == 1
        assert batches[0][1]["id"] == 2

@pytest.mark.asyncio
async def test_get_repo_languages(rest_client):
    mock_response = {"Python": 1000, "JavaScript": 500}
    with patch.object(rest_client, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await rest_client.get_repo_languages("owner/repo")
        assert response == mock_response
        mock_request.assert_called_once_with("GET", "repos/owner%2Frepo/languages", params={})

@pytest.mark.asyncio
async def test_get_file_content(rest_client):
    content = "test content"
    encoded_content = base64.b64encode(content.encode()).decode()
    mock_response = {
        "content": encoded_content,
        "encoding": "base64"
    }

    with patch.object(rest_client, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await rest_client.get_file_content("owner/repo", "test.txt")
        assert response == content
        mock_request.assert_called_once_with(
            "GET",
            "repos/owner%2Frepo/contents/test.txt",
            params={"ref": "main"}
        )

@pytest.mark.asyncio
async def test_get_file_data(rest_client):
    mock_response = {
        "name": "test.txt",
        "path": "test.txt",
        "content": "dGVzdCBjb250ZW50",
        "encoding": "base64"
    }

    mock_request = AsyncMock()
    mock_request.return_value = mock_response

    with patch.object(rest_client, "send_api_request", mock_request):
        response = await rest_client.get_file_data("owner/repo", "test.txt")
        assert response["name"] == "test.txt"
        assert response["content"] == "test content"
        mock_request.assert_called_once_with(
            "GET",
            "repos/owner%2Frepo/contents/test.txt",
            params={"ref": "main"}
        )

@pytest.mark.asyncio
async def test_get_page_links(rest_client):
    mock_response = MagicMock()
    mock_response.headers = {
        "Link": '<https://api.github.com/page2>; rel="next", <https://api.github.com/page1>; rel="prev"'
    }

    links = await rest_client.get_page_links(mock_response)
    assert links["next"] == "https://api.github.com/page2"
    assert links["prev"] == "https://api.github.com/page1"

@pytest.mark.asyncio
async def test_get_paginated_resource_with_search_api(rest_client):
    # Mock response for search API format
    mock_response = MagicMock()
    mock_response.is_success = True
    mock_response.json.return_value = {
        "items": [{"id": 1}, {"id": 2}],
        "next_page": None  # Set to None to indicate no more pages
    }
    mock_response.headers = {}

    with patch.object(rest_client._client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        batches = []
        async for batch in rest_client.get_paginated_resource("search/repositories"):
            batches.append(batch)
            if len(batches) >= 1:  # Safety check to prevent infinite loops
                break

        assert len(batches) == 1
        assert len(batches[0]) == 2
        assert batches[0][0]["id"] == 1
        assert batches[0][1]["id"] == 2
