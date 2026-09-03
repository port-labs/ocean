"""Tests for Harbor API client."""

import pytest
from unittest.mock import MagicMock
from harbor.clients import HarborClient, ArtifactFilter, RepositoryFilter, ProjectFilter


# Authentication Tests
@pytest.mark.asyncio
async def test_client_passes_auth_credentials(harbor_client, mock_http_client):
    """Test that client passes authentication credentials in requests."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_response.content = b"content"

    mock_http_client.request.return_value = mock_response

    async for _ in harbor_client.get_projects():
        pass

    call_args = mock_http_client.request.call_args
    assert call_args.kwargs["auth"] == ("admin", "Harbor12345")


@pytest.mark.asyncio
async def test_client_constructs_correct_api_url():
    """Test that client constructs correct API URL."""
    client = HarborClient(
        harbor_host="https://harbor.example.com/",
        harbor_username="user",
        harbor_password="pass",
    )

    assert client.harbor_host == "https://harbor.example.com"
    assert client.api_url == "https://harbor.example.com/api/v2.0"


# Pagination Tests
@pytest.mark.asyncio
async def test_get_projects_pagination(harbor_client, mock_http_client):
    """Test pagination through multiple pages of projects."""
    harbor_client.page_size = 2

    async def mock_request_with_pagination(*args, **kwargs):
        params = kwargs.get("params", {})
        page = params.get("page", 1)

        if page == 1:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"project_id": 1, "name": "project1"},
                {"project_id": 2, "name": "project2"},
            ]
            mock_response.content = b"content"
            return mock_response
        elif page == 2:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [{"project_id": 3, "name": "project3"}]
            mock_response.content = b"content"
            return mock_response
        else:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = []
            mock_response.content = b"content"
            return mock_response

    mock_http_client.request = mock_request_with_pagination

    projects = []
    async for project in harbor_client.get_projects():
        projects.append(project)

    assert len(projects) == 3
    assert projects[0]["name"] == "project1"
    assert projects[2]["name"] == "project3"


@pytest.mark.asyncio
async def test_error_handling_in_pagination(harbor_client, mock_http_client):
    """Test that pagination handles errors gracefully."""
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = [{"project_id": 1, "name": "project1"}]
    mock_response_success.content = b"content"

    mock_http_client.request.side_effect = [mock_response_success, Exception("Network error")]

    projects = []
    async for project in harbor_client.get_projects():
        projects.append(project)

    assert len(projects) == 1
    assert projects[0]["name"] == "project1"


# Project Filter Tests
@pytest.mark.asyncio
async def test_get_projects_with_filters(harbor_client, mock_http_client):
    """Test fetching projects with visibility and name filters."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"project_id": 1, "name": "public-project", "metadata": {"public": "true"}}]
    mock_response.content = b"content"

    mock_http_client.request.return_value = mock_response

    projects = []
    async for project in harbor_client.get_projects(public=True, name_prefix="public"):
        projects.append(project)

    assert len(projects) == 1
    assert projects[0]["name"] == "public-project"

    call_args = mock_http_client.request.call_args
    params = call_args.kwargs["params"]
    assert params["public"] == "true"
    assert params["name"] == "~public"


@pytest.mark.asyncio
async def test_get_all_repositories_with_project_filter(harbor_client, mock_http_client):
    """Test get_all_repositories filters by project visibility."""
    mock_projects_response = MagicMock()
    mock_projects_response.status_code = 200
    mock_projects_response.json.return_value = [
        {"project_id": 1, "name": "public-project", "metadata": {"public": "true"}}
    ]
    mock_projects_response.content = b"content"

    mock_repos_response = MagicMock()
    mock_repos_response.status_code = 200
    mock_repos_response.json.return_value = [{"name": "public-project/nginx"}]
    mock_repos_response.content = b"content"

    mock_http_client.request.side_effect = [
        mock_projects_response,
        mock_repos_response,
        MagicMock(status_code=200, json=lambda: [], content=b""),
    ]

    project_filter = ProjectFilter(visibility="public", name_prefix="public")
    repositories = []
    async for project, repo in harbor_client.get_all_repositories(project_filter, None):
        repositories.append((project, repo))

    assert len(repositories) == 1
    assert repositories[0][0]["name"] == "public-project"

    # Verify the filter params were passed
    first_call_args = mock_http_client.request.call_args_list[0]
    params = first_call_args.kwargs["params"]
    assert params["public"] == "true"
    assert params["name"] == "~public"


# Repository Filter Tests
@pytest.mark.asyncio
async def test_repository_filter_name_starts_with(harbor_client, mock_http_client):
    """Test filtering repositories by name prefix."""
    mock_projects_response = MagicMock()
    mock_projects_response.status_code = 200
    mock_projects_response.json.return_value = [{"project_id": 1, "name": "library"}]
    mock_projects_response.content = b"content"

    mock_repos_response = MagicMock()
    mock_repos_response.status_code = 200
    mock_repos_response.json.return_value = [
        {"name": "library/nginx"},
        {"name": "library/redis"},
        {"name": "library/app-service"},
    ]
    mock_repos_response.content = b"content"

    mock_http_client.request.side_effect = [
        mock_projects_response,
        mock_repos_response,
        MagicMock(status_code=200, json=lambda: [], content=b""),
    ]

    repository_filter = RepositoryFilter(name_starts_with="app")
    repositories = []
    async for project, repo in harbor_client.get_all_repositories(None, repository_filter):
        repositories.append(repo)

    assert len(repositories) == 1
    assert repositories[0]["name"] == "library/app-service"


@pytest.mark.asyncio
async def test_get_all_repositories_with_combined_filters(harbor_client, mock_http_client):
    """Test get_all_repositories with both project and repository filters."""
    mock_projects_response = MagicMock()
    mock_projects_response.status_code = 200
    mock_projects_response.json.return_value = [{"project_id": 1, "name": "myproject"}]
    mock_projects_response.content = b"content"

    mock_repos_response = MagicMock()
    mock_repos_response.status_code = 200
    mock_repos_response.json.return_value = [
        {"name": "myproject/api-service"},
        {"name": "myproject/web-app"},
        {"name": "myproject/api-gateway"},
    ]
    mock_repos_response.content = b"content"

    mock_http_client.request.side_effect = [
        mock_projects_response,
        mock_repos_response,
        MagicMock(status_code=200, json=lambda: [], content=b""),
    ]

    project_filter = ProjectFilter(name_prefix="my")
    repository_filter = RepositoryFilter(name_starts_with="api")

    repositories = []
    async for project, repo in harbor_client.get_all_repositories(project_filter, repository_filter):
        repositories.append(repo)

    assert len(repositories) == 2
    assert all("api" in repo["name"] for repo in repositories)


# User Tests
@pytest.mark.asyncio
async def test_get_users(harbor_client, mock_http_client):
    """Test fetching users."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"user_id": 1, "username": "admin", "email": "admin@example.com"},
        {"user_id": 2, "username": "user1", "email": "user1@example.com"},
    ]
    mock_response.content = b"content"

    mock_http_client.request.return_value = mock_response

    users = []
    async for user in harbor_client.get_users():
        users.append(user)

    assert len(users) == 2
    assert users[0]["username"] == "admin"
    assert users[1]["email"] == "user1@example.com"


# Repository Tests
@pytest.mark.asyncio
async def test_get_repositories(harbor_client, mock_http_client):
    """Test fetching repositories for a project."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"name": "library/nginx", "artifact_count": 5, "pull_count": 100},
        {"name": "library/redis", "artifact_count": 3, "pull_count": 50},
    ]
    mock_response.content = b"content"

    mock_http_client.request.return_value = mock_response

    repositories = []
    async for repo in harbor_client.get_repositories("library"):
        repositories.append(repo)

    assert len(repositories) == 2
    assert repositories[0]["name"] == "library/nginx"
    assert repositories[0]["artifact_count"] == 5


# Artifact Tests
@pytest.mark.asyncio
async def test_get_artifacts_with_scan_overview(harbor_client, mock_http_client):
    """Test fetching artifacts with scan overview data."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "digest": "sha256:abc123",
            "size": 1024,
            "tags": [{"name": "latest"}],
            "scan_overview": {
                "application/vnd.scanner.adapter.vuln.report.harbor+json; version=1.0": {
                    "scan_status": "Success",
                    "severity": "High",
                    "summary": {"summary": {"Critical": 5, "High": 10, "Medium": 20}},
                }
            },
        }
    ]
    mock_response.content = b"content"

    mock_http_client.request.return_value = mock_response

    artifacts = []
    async for artifact in harbor_client.get_artifacts("library", "nginx"):
        artifacts.append(artifact)

    assert len(artifacts) == 1
    assert artifacts[0]["digest"] == "sha256:abc123"
    assert "scan_overview" in artifacts[0]


@pytest.mark.asyncio
async def test_parallel_artifact_fetching(harbor_client, mock_http_client):
    """Test parallel fetching of artifacts across repositories."""
    mock_projects_response = MagicMock()
    mock_projects_response.status_code = 200
    mock_projects_response.json.return_value = [{"project_id": 1, "name": "project1"}]
    mock_projects_response.content = b"content"

    mock_repos_response = MagicMock()
    mock_repos_response.status_code = 200
    mock_repos_response.json.return_value = [{"name": "project1/repo1"}, {"name": "project1/repo2"}]
    mock_repos_response.content = b"content"

    mock_artifacts_response = MagicMock()
    mock_artifacts_response.status_code = 200
    mock_artifacts_response.json.return_value = [{"digest": "sha256:abc", "tags": []}]
    mock_artifacts_response.content = b"content"

    mock_http_client.request.side_effect = [
        mock_projects_response,
        mock_repos_response,
        mock_artifacts_response,
        mock_artifacts_response,
        MagicMock(status_code=200, json=lambda: [], content=b""),
    ]

    artifacts = []
    async for project, repository, artifact in harbor_client.get_all_artifacts():
        artifacts.append(artifact)

    assert len(artifacts) >= 1


# Artifact Filter Tests
@pytest.mark.asyncio
async def test_artifact_filter_by_severity(harbor_client):
    """Test filtering artifacts by minimum severity."""
    artifact_high = {"digest": "sha256:high", "scan_overview": {"test": {"severity": "High"}}}
    artifact_low = {"digest": "sha256:low", "scan_overview": {"test": {"severity": "Low"}}}

    artifact_filter = ArtifactFilter(min_severity="high")

    assert harbor_client._artifact_matches_filter(artifact_high, artifact_filter) is True
    assert harbor_client._artifact_matches_filter(artifact_low, artifact_filter) is False


@pytest.mark.asyncio
async def test_artifact_filter_by_tag(harbor_client):
    """Test filtering artifacts by tag name."""
    artifact_with_tag = {"digest": "sha256:abc", "tags": [{"name": "latest"}, {"name": "v1.0"}]}
    artifact_without_tag = {"digest": "sha256:def", "tags": [{"name": "dev"}]}
    artifact_no_tags = {"digest": "sha256:ghi", "tags": []}

    tag_filter = ArtifactFilter(tag="latest")

    assert harbor_client._artifact_matches_filter(artifact_with_tag, tag_filter) is True
    assert harbor_client._artifact_matches_filter(artifact_without_tag, tag_filter) is False
    assert harbor_client._artifact_matches_filter(artifact_no_tags, tag_filter) is False


@pytest.mark.asyncio
async def test_artifact_filter_by_digest(harbor_client):
    """Test filtering artifacts by digest prefix."""
    artifact = {"digest": "sha256:abc123def456"}

    assert harbor_client._artifact_matches_filter(artifact, ArtifactFilter(digest="sha256:abc")) is True
    assert harbor_client._artifact_matches_filter(artifact, ArtifactFilter(digest="sha256:xyz")) is False


@pytest.mark.asyncio
async def test_artifact_filter_by_label(harbor_client):
    """Test filtering artifacts by label."""
    artifact_with_label = {"digest": "sha256:abc", "labels": [{"name": "production"}, {"name": "verified"}]}
    artifact_without_label = {"digest": "sha256:def", "labels": [{"name": "development"}]}

    label_filter = ArtifactFilter(label="production")

    assert harbor_client._artifact_matches_filter(artifact_with_label, label_filter) is True
    assert harbor_client._artifact_matches_filter(artifact_without_label, label_filter) is False


@pytest.mark.asyncio
async def test_artifact_filter_by_media_type(harbor_client):
    """Test filtering artifacts by media type."""
    artifact_docker = {"digest": "sha256:abc", "media_type": "application/vnd.docker.distribution.manifest.v2+json"}
    artifact_oci = {"digest": "sha256:def", "media_type": "application/vnd.oci.image.manifest.v1+json"}

    docker_filter = ArtifactFilter(media_type="docker")

    assert harbor_client._artifact_matches_filter(artifact_docker, docker_filter) is True
    assert harbor_client._artifact_matches_filter(artifact_oci, docker_filter) is False


@pytest.mark.asyncio
async def test_artifact_filter_by_created_since(harbor_client):
    """Test filtering artifacts by creation date."""
    artifact_new = {"digest": "sha256:abc", "push_time": "2024-06-15T10:00:00Z"}
    artifact_old = {"digest": "sha256:def", "push_time": "2024-01-01T10:00:00Z"}

    date_filter = ArtifactFilter(created_since="2024-06-01T00:00:00Z")

    assert harbor_client._artifact_matches_filter(artifact_new, date_filter) is True
    assert harbor_client._artifact_matches_filter(artifact_old, date_filter) is False


@pytest.mark.asyncio
async def test_artifact_filter_combined(harbor_client):
    """Test filtering artifacts with multiple filter criteria."""
    artifact = {
        "digest": "sha256:abc123",
        "tags": [{"name": "latest"}],
        "labels": [{"name": "production"}],
        "media_type": "application/vnd.docker.distribution.manifest.v2+json",
        "push_time": "2024-06-15T10:00:00Z",
        "scan_overview": {"test": {"severity": "High"}},
    }

    combined_filter = ArtifactFilter(tag="latest", label="production", min_severity="medium")
    assert harbor_client._artifact_matches_filter(artifact, combined_filter) is True

    failing_filter = ArtifactFilter(tag="latest", label="staging")
    assert harbor_client._artifact_matches_filter(artifact, failing_filter) is False
