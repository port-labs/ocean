import asyncio
import gitlab
from unittest.mock import AsyncMock, patch, MagicMock
from client import GitLabHandler, KindNotImplementedException
from port_ocean.context.ocean import ocean, PortOceanContext
from gitlab.v4.objects import Project
import pytest
import yaml
import jq

@pytest.fixture
def mock_ocean():
    with patch('port_ocean.context.ocean.ocean', spec=PortOceanContext) as mock_ocean:
        mock_ocean.integration_config = {
            "gitlab_token": "mock_token",
            "gitlab_url": "https://mock_url",
            "gitlab_secret": "mock_secret"
        }
        mock_ocean.config.port.base_url = "mock_port_url"
        yield mock_ocean

@pytest.fixture
def mock_gitlab_handler(mock_ocean):
    with patch('client.GitLabHandler', spec=GitLabHandler) as mock_handler:
        mock_instance = mock_handler.return_value
        mock_instance.fetch_data = AsyncMock()
        mock_instance.fetch_project = AsyncMock()
        mock_instance.generic_handler = AsyncMock()
        mock_instance.webhook_handler = AsyncMock()
        mock_instance.system_hook_handler = AsyncMock()
        mock_instance.patch_entity = AsyncMock()
        mock_instance.client = MagicMock()
        mock_instance.client.put = AsyncMock()
        mock_instance.mappings = {
            "project": {
                "identifier": ".name",
                "title": ".name",
                "blueprint": "project",
                "properties": {
                    "name": ".name",
                    "description": ".description",
                    "createdAt": ".created_at",
                    "updatedAt": ".updated_at"
                },
                "relations": {
                    "service": ".service"
                }
            },
            "group": {
                "identifier": ".name",
                "title": ".name",
                "blueprint": "group",
                "properties": {
                    "name": ".name",
                    "path": ".path"
                },
                "relations": {
                    "service": ".service"
                }
            },
            "merge_request": {
                "identifier": ".iid",
                "title": ".title",
                "blueprint": "merge_request",
                "properties": {
                    "title": ".title",
                    "description": ".description",
                    "createdAt": ".created_at",
                    "updatedAt": ".updated_at"
                },
                "relations": {
                    "service": ".service"
                }
            },
            "issue": {
                "identifier": ".iid",
                "title": ".title",
                "blueprint": "issue",
                "properties": {
                    "title": ".title",
                    "description": ".description",
                    "createdAt": ".created_at",
                    "updatedAt": ".updated_at"
                },
                "relations": {
                    "service": ".service"
                }
            }
        }
        yield mock_instance

@pytest.fixture
def init_ocean():
    # Initialize the PortOcean context
    ocean._app = MagicMock()
    ocean._app.config = MagicMock()
    ocean._app.config.integration = MagicMock()
    ocean._app.config.integration.config = {
        "gitlab_token": "mock_token",
        "gitlab_url": "https://mock_url",
        "gitlab_secret": "mock_secret"
    }
    ocean._app.config.port = MagicMock()
    ocean._app.config.port.base_url = "mock_port_url"
    yield
    # Clean up
    ocean._app = None

@pytest.mark.asyncio
@patch('client.AsyncFetcher.fetch_single', new_callable=AsyncMock)
async def test_fetch_project_success(mock_fetch_single, mock_ocean, mock_gitlab_handler, init_ocean):
    # Arrange
    mock_project = MagicMock(spec=Project)
    mock_project.files = MagicMock()  # Ensure the project object has the files attribute
    mock_fetch_single.return_value = mock_project
    handler = GitLabHandler()

    # Act
    project = await handler.fetch_project("123")

    # Assert
    assert project == mock_project
    mock_fetch_single.assert_called_once_with("https://mock_url", "mock_token", "123")

@pytest.mark.asyncio
async def test_patch_entity_success(mock_ocean, mock_gitlab_handler, init_ocean):
    # Arrange
    mock_port_headers = {"Authorization": "Bearer mock_token"}
    mock_response = MagicMock(status_code=200, json=AsyncMock(return_value={"success": True}))
    mock_gitlab_handler.client.put = AsyncMock(return_value=mock_response)
    handler = GitLabHandler()

    # Act
    result = await handler.patch_entity("blueprint1", "entity1", {"key": "value"})

    # Assert
    assert result == {"success": True}
    mock_gitlab_handler.client.put.assert_called_once_with(
        "mock_port_url/v1/blueprints/blueprint1/entities/entity1",
        json={"key": "value"},
        headers=mock_port_headers
    )

@pytest.mark.asyncio
async def test_patch_entity_failure(mock_ocean, mock_gitlab_handler, init_ocean):
    # Arrange
    mock_response = MagicMock(status_code=400, json=AsyncMock(return_value={"error": "Bad Request"}))
    mock_gitlab_handler.client.put = AsyncMock(return_value=mock_response)
    handler = GitLabHandler()

    # Act
    result = await handler.patch_entity("blueprint1", "entity1", {"key": "value"})

    # Assert
    assert result == {"error": "Bad Request"}
    mock_gitlab_handler.client.put.assert_called_once_with(
        "mock_port_url/v1/blueprints/blueprint1/entities/entity1",
        json={"key": "value"},
        headers={"Authorization": "Bearer mock_token"}
    )

@pytest.mark.asyncio
async def test_generic_handler_success(mock_ocean, mock_gitlab_handler, init_ocean):
    # Arrange
    data = {
        "name": "Mock Project",
        "description": "This is a mock project",
        "created_at": "2023-10-01T12:34:56Z",
        "updated_at": "2023-10-01T12:34:56Z",
        "service": "mock_service"
    }
    kind = "project"
    mock_project = MagicMock(spec=Project)
    mock_project.files = MagicMock()  # Ensure the project object has the files attribute
    mock_gitlab_handler.fetch_project.return_value = mock_project
    handler = GitLabHandler()

    # Act
    await handler.generic_handler(data, kind)

    # Assert
    mock_gitlab_handler.fetch_project.assert_called_once_with("mock_service")
    mock_gitlab_handler.generic_handler.assert_called_once_with(data, kind)

@pytest.mark.asyncio
async def test_generic_handler_failure(mock_ocean, mock_gitlab_handler, init_ocean):
    # Arrange
    data = {
        "name": "Mock Project",
        "description": "This is a mock project",
        "created_at": "2023-10-01T12:34:56Z",
        "updated_at": "2023-10-01T12:34:56Z",
        "service": "mock_service"
    }
    kind = "unsupported_kind"
    handler = GitLabHandler()

    # Act & Assert
    with pytest.raises(KindNotImplementedException) as e:
        await handler.generic_handler(data, kind)

    assert str(e.value) == "Unsupported kind: unsupported_kind. Available kinds: group, project, merge_request, issue"

@pytest.mark.asyncio
async def test_webhook_handler_success(mock_ocean, mock_gitlab_handler, init_ocean):
    # Arrange
    data = {
        "object_kind": "project",
        "name": "Mock Project",
        "description": "This is a mock project",
        "created_at": "2023-10-01T12:34:56Z",
        "updated_at": "2023-10-01T12:34:56Z",
        "service": "mock_service"
    }
    handler = GitLabHandler()

    # Act
    await handler.webhook_handler(data)

    # Assert
    mock_gitlab_handler.webhook_handler.assert_called_once_with(data)

@pytest.mark.asyncio
async def test_system_hook_handler_success(mock_ocean, mock_gitlab_handler, init_ocean):
    # Arrange
    data = {
        "event_name": "project_create",
        "name": "Mock Project",
        "description": "This is a mock project",
        "created_at": "2023-10-01T12:34:56Z",
        "updated_at": "2023-10-01T12:34:56Z",
        "service": "mock_service"
    }
    handler = GitLabHandler()

    # Act
    await handler.system_hook_handler(data)

    # Assert
    mock_gitlab_handler.system_hook_handler.assert_called_once_with(data)

@pytest.mark.asyncio
async def test_fetch_data_success(mock_ocean, mock_gitlab_handler, init_ocean):
    # Arrange
    mock_gitlab_handler.fetch_data.return_value = AsyncMock()
    mock_gitlab_handler.fetch_data.return_value.__aiter__.return_value = AsyncMock()
    mock_gitlab_handler.fetch_data.return_value.__aiter__.return_value.__anext__.side_effect = [({"key": "value"},), StopAsyncIteration()]
    handler = GitLabHandler()

    # Act
    results = []
    async for page in handler.fetch_data("/groups"):
        results.extend(page)

    # Assert
    assert results == [{"key": "value"}]
    mock_gitlab_handler.fetch_data.assert_called_once_with("/groups", params=None)