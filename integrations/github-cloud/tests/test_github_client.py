import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from github_cloud.clients.github_client import GitHubCloudClient

@pytest.fixture
def github_client():
    return GitHubCloudClient("https://api.github.com", "test_token")

@pytest.mark.asyncio
async def test_get_repository(github_client):
    mock_response = {"name": "test-repo", "full_name": "owner/test-repo"}
    with patch.object(github_client.rest, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await github_client.get_repository("owner/test-repo")
        assert response == mock_response
        mock_request.assert_called_once_with("GET", "repos/owner%2Ftest-repo")

@pytest.mark.asyncio
async def test_get_organization(github_client):
    mock_response = {"login": "test-org", "name": "Test Organization"}
    with patch.object(github_client.rest, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await github_client.get_organization("test-org")
        assert response == mock_response
        mock_request.assert_called_once_with("GET", "orgs/test-org")

@pytest.mark.asyncio
async def test_get_pull_request(github_client):
    mock_response = {"number": 1, "title": "Test PR"}
    with patch.object(github_client.rest, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await github_client.get_pull_request("owner/repo", 1)
        assert response == mock_response
        mock_request.assert_called_once_with("GET", "repos/owner/repo/pulls/1")

@pytest.mark.asyncio
async def test_get_issue(github_client):
    mock_response = {"number": 1, "title": "Test Issue"}
    with patch.object(github_client.rest, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await github_client.get_issue("owner/repo", 1)
        assert response == mock_response
        mock_request.assert_called_once_with("GET", "repos/owner/repo/issues/1")

@pytest.mark.asyncio
async def test_get_workflow_run(github_client):
    mock_response = {"id": 1, "name": "Test Workflow"}
    with patch.object(github_client.rest, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await github_client.get_workflow_run("owner/repo", 1)
        assert response == mock_response
        mock_request.assert_called_once_with("GET", "repos/owner/repo/actions/runs/1")

@pytest.mark.asyncio
async def test_get_workflow_job(github_client):
    mock_response = {"id": 1, "name": "Test Job"}
    with patch.object(github_client.rest, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await github_client.get_workflow_job("owner/repo", 1)
        assert response == mock_response
        mock_request.assert_called_once_with("GET", "repos/owner/repo/actions/jobs/1")

@pytest.mark.asyncio
async def test_get_team_member(github_client):
    mock_response = {"login": "test-user", "type": "User"}
    with patch.object(github_client.rest, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await github_client.get_team_member("test-org", "test-team", "test-user")
        assert response == mock_response
        mock_request.assert_called_once_with("GET", "orgs/test-org/teams/test-team/members/test-user")

@pytest.mark.asyncio
async def test_get_repositories_with_languages(github_client):
    mock_repos = [{"full_name": "owner/repo1"}]
    mock_languages = {"Python": 1000, "JavaScript": 500}

    async def mock_paginated(*args, **kwargs):
        yield mock_repos

    with patch.object(github_client.rest, "get_paginated_resource", mock_paginated):
        with patch.object(github_client, "_enrich_repo_with_languages", new_callable=AsyncMock) as mock_enrich:
            mock_enrich.return_value = {"full_name": "owner/repo1", "languages": mock_languages}
            async for batch in github_client.get_repositories(include_languages=True):
                assert len(batch) == 1
                assert batch[0]["languages"] == mock_languages

@pytest.mark.asyncio
async def test_get_file_content(github_client):
    mock_response = {
        "content": "base64_encoded_content",
        "encoding": "base64"
    }
    with patch.object(github_client.rest, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await github_client.get_file_content("owner/repo", "path/to/file.txt")
        assert response is not None
        mock_request.assert_called_once_with(
            "GET",
            "repos/owner/repo/contents/path/to/file.txt",
            params={"ref": "main"}
        )

@pytest.mark.asyncio
async def test_file_exists(github_client):
    with patch.object(github_client.rest, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {"name": "test.txt"}
        exists = await github_client.file_exists("owner/repo", "test.txt")
        assert exists is True

        mock_request.side_effect = Exception("File not found")
        exists = await github_client.file_exists("owner/repo", "nonexistent.txt")
        assert exists is False

@pytest.mark.asyncio
async def test_search_files(github_client):
    mock_response = {
        "items": [
            {
                "name": "test.json",
                "path": "path/to/test.json",
                "repository": {"full_name": "owner/repo"}
            }
        ]
    }

    async def mock_paginated(*args, **kwargs):
        yield mock_response["items"]

    with patch.object(github_client.rest, "get_paginated_resource", mock_paginated):
        async for batch in github_client.search_files("test", "path"):
            assert len(batch) == 1
            assert batch[0]["name"] == "test.json"

@pytest.mark.asyncio
async def test_get_team_members(github_client):
    mock_members = [
        {"login": "user1", "type": "User"},
        {"login": "user2", "type": "User"}
    ]

    async def mock_paginated(*args, **kwargs):
        yield mock_members

    with patch.object(github_client.rest, "get_paginated_resource", mock_paginated):
        async for batch in github_client.get_team_members("test-org", "test-team"):
            assert len(batch) == 2
            assert batch[0]["login"] == "user1"
            assert batch[1]["login"] == "user2"

@pytest.mark.asyncio
async def test_get_team_member(github_client):
    mock_response = {"login": "test-user", "type": "User"}
    with patch.object(github_client.rest, "send_api_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        response = await github_client.get_team_member("test-org", "test-team", "test-user")
        assert response == mock_response
        mock_request.assert_called_once_with("GET", "orgs/test-org/teams/test-team/members/test-user")
