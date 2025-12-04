import pytest
import respx
import httpx
from client import HarborClient


class TestHarborClient:
    """Tests for HarborClient."""

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client for testing."""
        return httpx.AsyncClient()

    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_harbor_config, mock_http_client):
        """Test client initialization."""
        client = HarborClient(
            harbor_url=mock_harbor_config["harbor_url"],
            username=mock_harbor_config["username"],
            password=mock_harbor_config["password"],
            http_client=mock_http_client,
        )

        assert client.harbor_url == "http://localhost:8081"
        assert client.api_url == "http://localhost:8081/api/v2.0"
        assert client.username == "admin"
        assert client.password == "Harbor12345"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_paginated_projects(
        self, mock_harbor_config, mock_project_data, mock_http_client
    ):
        """Test fetching paginated projects."""
        client = HarborClient(
            **mock_harbor_config,
            http_client=mock_http_client,
        )

        respx.get("http://localhost:8081/api/v2.0/projects").mock(
            return_value=httpx.Response(
                200,
                json=mock_project_data,
                headers={"X-Total-Count": "2"},
            )
        )

        projects = []
        async for batch in client.get_paginated_projects():
            projects.extend(batch)

        assert len(projects) == 2
        assert projects[0]["name"] == "library"
        assert projects[1]["name"] == "ocean-integration"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_paginated_projects_with_filters(
        self, mock_harbor_config, mock_project_data, mock_http_client
    ):
        """Test fetching projects with filters."""
        client = HarborClient(
            **mock_harbor_config,
            http_client=mock_http_client,
        )

        respx.get("http://localhost:8081/api/v2.0/projects").mock(
            return_value=httpx.Response(
                200,
                json=[mock_project_data[0]],
                headers={"X-Total-Count": "1"},
            )
        )

        projects = []
        async for batch in client.get_paginated_projects({"public": True}):
            projects.extend(batch)

        assert len(projects) == 1
        assert projects[0]["metadata"]["public"] == "true"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_single_project(
        self, mock_harbor_config, mock_project_data, mock_http_client
    ):
        """Test fetching a single project."""
        client = HarborClient(
            **mock_harbor_config,
            http_client=mock_http_client,
        )

        respx.get("http://localhost:8081/api/v2.0/projects/library").mock(
            return_value=httpx.Response(200, json=mock_project_data[0])
        )

        project = await client.get_project("library")

        assert project["name"] == "library"
        assert project["project_id"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_paginated_users(
        self, mock_harbor_config, mock_user_data, mock_http_client
    ):
        """Test fetching paginated users."""
        client = HarborClient(
            **mock_harbor_config,
            http_client=mock_http_client,
        )

        respx.get("http://localhost:8081/api/v2.0/users").mock(
            return_value=httpx.Response(
                200,
                json=mock_user_data,
                headers={"X-Total-Count": "2"},
            )
        )

        users = []
        async for batch in client.get_paginated_users():
            users.extend(batch)

        assert len(users) == 2
        assert users[0]["username"] == "admin"
        assert users[1]["username"] == "developer"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_paginated_repositories(
        self, mock_harbor_config, mock_repository_data, mock_http_client
    ):
        """Test fetching paginated repositories."""
        client = HarborClient(
            **mock_harbor_config,
            http_client=mock_http_client,
        )

        respx.get(
            "http://localhost:8081/api/v2.0/projects/ocean-integration/repositories"
        ).mock(
            return_value=httpx.Response(
                200,
                json=mock_repository_data,
                headers={"X-Total-Count": "2"},
            )
        )

        repos = []
        async for batch in client.get_paginated_repositories("ocean-integration"):
            repos.extend(batch)

        assert len(repos) == 2
        assert repos[0]["name"] == "ocean-integration/redis"
        assert repos[1]["name"] == "ocean-integration/nginx"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_paginated_artifacts(
        self, mock_harbor_config, mock_artifact_data, mock_http_client
    ):
        """Test fetching paginated artifacts."""
        client = HarborClient(
            **mock_harbor_config,
            http_client=mock_http_client,
        )

        respx.get(
            "http://localhost:8081/api/v2.0/projects/ocean-integration/repositories/redis/artifacts"
        ).mock(
            return_value=httpx.Response(
                200,
                json=mock_artifact_data,
                headers={"X-Total-Count": "1"},
            )
        )

        artifacts = []
        async for batch in client.get_paginated_artifacts("ocean-integration", "redis"):
            artifacts.extend(batch)

        assert len(artifacts) == 1
        assert (
            artifacts[0]["digest"]
            == "sha256:e19a92f6821ebdbfa6676b7133c594c7ea9c3702daf773f5064845b9f8642b93"
        )
        assert artifacts[0]["tags"][0]["name"] == "v1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_pagination_multiple_pages(
        self, mock_harbor_config, mock_http_client
    ):
        """Test pagination with multiple pages."""
        client = HarborClient(
            **mock_harbor_config,
            http_client=mock_http_client,
        )

        respx.get(
            "http://localhost:8081/api/v2.0/projects",
            params={"page": 1, "page_size": 100, "with_detail": True},
        ).mock(
            return_value=httpx.Response(
                200,
                json=[{"project_id": i, "name": f"project-{i}"} for i in range(100)],
                headers={"X-Total-Count": "150"},
            )
        )

        respx.get(
            "http://localhost:8081/api/v2.0/projects",
            params={"page": 2, "page_size": 100, "with_detail": True},
        ).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"project_id": i, "name": f"project-{i}"} for i in range(100, 150)
                ],
                headers={"X-Total-Count": "150"},
            )
        )

        all_projects = []
        async for batch in client.get_paginated_projects():
            all_projects.extend(batch)

        assert len(all_projects) == 150

    @pytest.mark.asyncio
    @respx.mock
    async def test_authentication_header(
        self, mock_harbor_config, mock_project_data, mock_http_client
    ):
        """Test that authentication header is included."""
        client = HarborClient(
            **mock_harbor_config,
            http_client=mock_http_client,
        )

        route = respx.get("http://localhost:8081/api/v2.0/projects").mock(
            return_value=httpx.Response(
                200,
                json=mock_project_data,
                headers={"X-Total-Count": "2"},
            )
        )

        async for _ in client.get_paginated_projects():
            pass

        assert route.called
        request = route.calls.last.request
        assert "authorization" in request.headers
