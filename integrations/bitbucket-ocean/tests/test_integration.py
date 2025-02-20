import pytest
from bitbucket_ocean.integration import BitbucketOceanIntegration
from bitbucket_ocean.config import CONFIG

@pytest.mark.asyncio
async def test_fetch_projects(mocker):
    mock_integration = BitbucketOceanIntegration(CONFIG)
    mocker.patch.object(mock_integration, "_fetch_paginated_data", return_value=[{"name": "Project 1"}])
    
    projects = await mock_integration.fetch_projects()
    
    assert len(projects) == 1
    assert projects[0]["name"] == "Project 1"
