import pytest
from unittest.mock import AsyncMock
from bit_bucket.bit_bucket_integration.integration import BitbucketOceanIntegration
from bit_bucket.bit_bucket_integration.config import CONFIG

@pytest.mark.asyncio
async def test_fetch_projects(mocker):
    """Test fetching projects with a mocked API response."""
    mock_integration = BitbucketOceanIntegration(CONFIG)
    
    # Mock `_fetch_paginated_data` method to return a sample project list
    mocker.patch.object(mock_integration, "_fetch_paginated_data", return_value=[{"name": "Project 1"}])

    projects = await mock_integration.fetch_projects()

    # Assertions
    assert isinstance(projects, list)
    assert len(projects) == 1
    assert projects[0]["name"] == "Project 1"

@pytest.mark.asyncio
async def test_fetch_projects_empty(mocker):
    """Test fetching projects when API returns an empty list."""
    mock_integration = BitbucketOceanIntegration(CONFIG)
    
    mocker.patch.object(mock_integration, "_fetch_paginated_data", return_value=[])

    projects = await mock_integration.fetch_projects()

    # Assertions
    assert isinstance(projects, list)
    assert len(projects) == 0  # No projects should be returned

@pytest.mark.asyncio
async def test_fetch_projects_error_handling(mocker):
    """Test fetching projects when an API call raises an exception."""
    mock_integration = BitbucketOceanIntegration(CONFIG)

    # Simulate an exception when calling `_fetch_paginated_data`
    mocker.patch.object(mock_integration, "_fetch_paginated_data", side_effect=Exception("API Error"))

    with pytest.raises(Exception, match="API Error"):
        await mock_integration.fetch_projects()