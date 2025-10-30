import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from harbor.utils.constants import HarborKind
from main import resync_projects, resync_users, resync_repositories, resync_artifacts


@pytest.mark.asyncio
async def test_can_successfully_resync_projects():
    mock_client = MagicMock()

    async def mock_projects():
        yield [{"project_id": 1, "name": "test-project"}]

    mock_client.get_paginated_resources = MagicMock(return_value=mock_projects())

    with patch("main.HarborClientFactory.get_client", return_value=mock_client):
        results = []
        async for batch in resync_projects(HarborKind.PROJECT):
            results.extend(batch)

        assert len(results) == 1
        assert results[0]["name"] == "test-project"
        mock_client.get_paginated_resources.assert_called_once_with(HarborKind.PROJECT)


@pytest.mark.asyncio
async def test_project_resync_with_errors_can_recover_gracefully():
    mock_client = MagicMock()
    mock_client.get_paginated_resources = MagicMock(side_effect=Exception("API Error"))

    with patch("main.HarborClientFactory.get_client", return_value=mock_client):
        with pytest.raises(Exception, match="API Error"):
            async for _ in resync_projects(HarborKind.PROJECT):
                pass


@pytest.mark.asyncio
async def test_can_successfully_resync_repos():
    mock_client = MagicMock()

    async def mock_projects():
        yield [{"project_id": 1, "name": "test-project"}]

    async def mock_repos():
        yield [{"id": 1, "name": "test-project/nginx"}]

    def get_paginated_side_effect(kind, **kwargs):
        if kind == HarborKind.PROJECT:
            return mock_projects()
        elif kind == HarborKind.REPOSITORY:
            return mock_repos()

    mock_client.get_paginated_resources = MagicMock(
        side_effect=get_paginated_side_effect
    )

    with patch("main.HarborClientFactory.get_client", return_value=mock_client):
        results = []
        async for batch in resync_repositories(HarborKind.REPOSITORY):
            results.extend(batch)

        assert len(results) == 1
        assert results[0]["name"] == "test-project/nginx"


@pytest.mark.asyncio
async def test_repo_resync_can_handle_errors_recovery_gracefully():
    mock_client = MagicMock()

    async def mock_projects():
        yield [
            {"project_id": 1, "name": "good-project"},
            {"project_id": 2, "name": "bad-project"},
        ]

    call_count = 0

    async def mock_repos():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield [{"id": 1, "name": "good-project/nginx"}]
        else:
            raise Exception("Project error")

    def get_paginated_side_effect(kind, **kwargs):
        if kind == HarborKind.PROJECT:
            return mock_projects()
        elif kind == HarborKind.REPOSITORY:
            return mock_repos()

    mock_client.get_paginated_resources = MagicMock(
        side_effect=get_paginated_side_effect
    )

    with patch("main.HarborClientFactory.get_client", return_value=mock_client):
        results = []
        async for batch in resync_repositories(HarborKind.REPOSITORY):
            results.extend(batch)

        # should get results from good project only
        assert len(results) == 1
        assert results[0]["name"] == "good-project/nginx"


@pytest.mark.asyncio
async def test_can_successfully_resync_artifacts():
    mock_client = MagicMock()

    async def mock_projects():
        yield [{"project_id": 1, "name": "test-project"}]

    async def mock_repos():
        yield [{"id": 1, "name": "test-project/nginx"}]

    async def mock_artifacts():
        yield [{"id": 1, "digest": "sha256:abc123"}]

    def get_paginated_side_effect(kind, **kwargs):
        if kind == HarborKind.PROJECT:
            return mock_projects()
        elif kind == HarborKind.REPOSITORY:
            return mock_repos()
        elif kind == HarborKind.ARTIFACT:
            return mock_artifacts()

    mock_client.get_paginated_resources = MagicMock(
        side_effect=get_paginated_side_effect
    )

    with patch("main.HarborClientFactory.get_client", return_value=mock_client):
        results = []
        async for batch in resync_artifacts(HarborKind.ARTIFACT):
            results.extend(batch)

        assert len(results) == 1
        assert results[0]["digest"] == "sha256:abc123"
