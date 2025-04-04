import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from main import (
    on_start,
    resync_repository,
    resync_issues,
    resync_pull_requests,
    resync_teams,
    resync_workflows,
)
from client import GitHubClient
from integration import (
    RepositoryResourceConfig,
    IssueResourceConfig,
    PullRequestResourceConfig,
    TeamResourceConfig,
    WorkflowResourceConfig,
    ObjectKind,
)


@pytest.fixture
def mock_client():
    with patch("main.get_client") as mock:
        client = AsyncMock(spec=GitHubClient)
        mock.return_value = client
        yield client


@pytest.fixture
def mock_ocean():
    with patch("main.ocean") as mock:
        yield mock


@pytest.fixture
def mock_event():
    with patch("main.event") as mock:
        yield mock


@pytest.mark.asyncio
async def test_on_start_with_once_listener(mock_ocean, mock_client):
    mock_ocean.event_listener_type = "ONCE"
    await on_start()
    mock_client.create_webhooks_if_not_exists.assert_not_called()


@pytest.mark.asyncio
async def test_on_start_with_webhook_listener(mock_ocean, mock_client):
    mock_ocean.event_listener_type = "WEBHOOK"
    await on_start()
    mock_client.create_webhooks_if_not_exists.assert_called_once()


@pytest.mark.asyncio
async def test_resync_repository(mock_client, mock_event):
    # Setup
    mock_event.resource_config = MagicMock(spec=RepositoryResourceConfig)
    mock_event.resource_config.selector.organizations = ["org1", "org2"]
    mock_client.get_repositories.return_value = [
        [{"name": "repo1", "owner": {"login": "org1"}}],
        [{"name": "repo2", "owner": {"login": "org2"}}],
    ]

    # Test
    result = []
    async for item in resync_repository(ObjectKind.REPOSITORY):
        result.append(item)

    # Assert
    assert len(result) == 2
    mock_client.get_repositories.assert_called_once_with(["org1", "org2"])


@pytest.mark.asyncio
async def test_resync_issues(mock_client, mock_event):
    # Setup
    mock_event.resource_config = MagicMock(spec=IssueResourceConfig)
    mock_event.resource_config.selector.organizations = ["org1"]
    mock_client.get_repositories.return_value = [
        [{"name": "repo1", "owner": {"login": "org1"}}]
    ]
    mock_client.get_issues.return_value = [
        [{"title": "issue1"}],
        [{"title": "issue2"}],
    ]

    # Test
    result = []
    async for item in resync_issues(ObjectKind.ISSUE):
        result.append(item)

    # Assert
    assert len(result) == 2
    mock_client.get_issues.assert_called()


@pytest.mark.asyncio
async def test_resync_pull_requests(mock_client, mock_event):
    # Setup
    mock_event.resource_config = MagicMock(spec=PullRequestResourceConfig)
    mock_event.resource_config.selector.organizations = ["org1"]
    mock_client.get_repositories.return_value = [
        [{"name": "repo1", "owner": {"login": "org1"}}]
    ]
    mock_client.get_pull_requests.return_value = [
        [{"title": "pr1"}],
        [{"title": "pr2"}],
    ]

    # Test
    result = []
    async for item in resync_pull_requests(ObjectKind.PULL_REQUEST):
        result.append(item)

    # Assert
    assert len(result) == 2
    mock_client.get_pull_requests.assert_called()


@pytest.mark.asyncio
async def test_resync_teams(mock_client, mock_event):
    # Setup
    mock_event.resource_config = MagicMock(spec=TeamResourceConfig)
    mock_event.resource_config.selector.organizations = ["org1"]
    mock_client.get_repositories.return_value = [
        [{"name": "repo1", "owner": {"login": "org1"}}]
    ]
    mock_client.get_teams.return_value = [
        [{"name": "team1"}],
        [{"name": "team2"}],
    ]

    # Test
    result = []
    async for item in resync_teams(ObjectKind.TEAM):
        result.append(item)

    # Assert
    assert len(result) == 2
    mock_client.get_teams.assert_called()


@pytest.mark.asyncio
async def test_resync_workflows(mock_client, mock_event):
    # Setup
    mock_event.resource_config = MagicMock(spec=WorkflowResourceConfig)
    mock_event.resource_config.selector.organizations = ["org1"]
    mock_client.get_repositories.return_value = [
        [{"name": "repo1", "owner": {"login": "org1"}}]
    ]
    mock_client.get_workflows.return_value = [
        [{"name": "workflow1"}],
        [{"name": "workflow2"}],
    ]

    # Test
    result = []
    async for item in resync_workflows(ObjectKind.WORKFLOW):
        result.append(item)

    # Assert
    assert len(result) == 2
    mock_client.get_workflows.assert_called() 