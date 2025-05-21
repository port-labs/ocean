import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture(autouse=True)
def mock_ocean():
    mock_ocean = MagicMock()
    mock_ocean.on_start = lambda: lambda x: x  # Return decorator that returns function unchanged
    mock_ocean.on_resync = lambda x=None: lambda y: y  # Same for on_resync
    mock_ocean.router = MagicMock()
    
    with patch('port_ocean.context.ocean.ocean', mock_ocean):
        yield mock_ocean

@pytest.mark.asyncio
async def test_sync_repositories():
    # Import main after mocking Ocean
    from main import sync_repositories
    
    # Mock GitHub client response
    mock_repo = {"id": 1, "name": "repo", "html_url": "http://url"}
    mock_client = AsyncMock()
    mock_client.get_repositories.return_value = [mock_repo]

    # Mock config
    mock_config = MagicMock()
    mock_config.github_org = "test-org"

    # Test the function
    result = await sync_repositories("repositories", mock_config, mock_client)
    
    # Verify results
    assert len(result) == 1
    assert result[0]["identifier"] == 1
    assert result[0]["title"] == "repo"
    
    # Verify client called correctly
    mock_client.get_repositories.assert_called_once_with("test-org")
