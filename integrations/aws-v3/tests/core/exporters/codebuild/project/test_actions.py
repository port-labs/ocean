import pytest
from unittest.mock import AsyncMock, MagicMock
from aws.core.exporters.codebuild.project.actions import (
    ListProjectsAction,
    GetProjectDetailsAction,
    GetProjectWebhooksAction,
)


@pytest.mark.asyncio
async def test_list_projects_action():
    """Test the ListProjectsAction processes project names correctly."""
    action = ListProjectsAction(MagicMock())
    
    projects = ["project1", "project2", "project3"]
    
    result = await action._execute(projects)
    
    assert len(result) == 3
    assert result[0]["name"] == "project1"
    assert result[0]["id"] == "project1"
    assert result[1]["name"] == "project2"
    assert result[1]["id"] == "project2"
    assert result[2]["name"] == "project3"
    assert result[2]["id"] == "project3"


@pytest.mark.asyncio
async def test_get_project_details_action():
    """Test the GetProjectDetailsAction fetches project details correctly."""
    action = GetProjectDetailsAction(AsyncMock())

    # Mock the batch_get_projects response
    mock_response = {
        "projects": [
            {
                "name": "test-project",
                "arn": "arn:aws:codebuild:us-east-1:123456789012:project/test-project",
                "description": "Test project description",
                "serviceRole": "arn:aws:iam::123456789012:role/service-role/codebuild-test-service-role",
                "timeoutInMinutes": 60,
                "source": {
                    "type": "GITHUB",
                    "location": "https://github.com/example/repo.git"
                },
                "environment": {
                    "type": "LINUX_CONTAINER",
                    "image": "aws/codebuild/amazonlinux2-x86_64-standard:3.0",
                    "computeType": "BUILD_GENERAL1_MEDIUM"
                },
                "artifacts": {
                    "type": "NO_ARTIFACTS"
                },
                "tags": []
            }
        ]
    }
    
    action.client.batch_get_projects.return_value = mock_response
    
    resources = ["test-project"]
    result = await action._execute(resources)
    
    assert len(result) == 1
    project = result[0]
    assert project["name"] == "test-project"
    assert project["arn"] == "arn:aws:codebuild:us-east-1:123456789012:project/test-project"
    assert project["description"] == "Test project description"
    assert project["serviceRole"] == "arn:aws:iam::123456789012:role/service-role/codebuild-test-service-role"
    assert project["timeoutInMinutes"] == 60


@pytest.mark.asyncio
async def test_get_project_details_action_empty_resources():
    """Test the GetProjectDetailsAction with empty resources list."""
    action = GetProjectDetailsAction(AsyncMock())

    result = await action._execute([])
    
    assert result == []
    action.client.batch_get_projects.assert_not_called()


@pytest.mark.asyncio
async def test_get_project_webhooks_action():
    """Test the GetProjectWebhooksAction fetches webhooks correctly."""
    action = GetProjectWebhooksAction(AsyncMock())

    # Mock the list_webhooks_for_project response
    mock_response = {
        "webhooks": [
            {
                "url": "https://codebuild.us-east-1.amazonaws.com/webhooks?12345",
                "payloadUrl": "https://codebuild.us-east-1.amazonaws.com/webhooks?12345",
                "secret": "secret123"
            }
        ]
    }
    
    action.client.list_webhooks_for_project.return_value = mock_response
    
    resources = ["test-project"]
    result = await action._execute(resources)
    
    assert len(result) == 1
    webhook_data = result[0]
    assert "webhook" in webhook_data
    assert len(webhook_data["webhook"]) == 1
    assert webhook_data["webhook"][0]["url"] == "https://codebuild.us-east-1.amazonaws.com/webhooks?12345"


@pytest.mark.asyncio
async def test_get_project_webhooks_action_resource_not_found():
    """Test the GetProjectWebhooksAction handles ResourceNotFoundException."""
    action = GetProjectWebhooksAction(AsyncMock())

    # Mock ClientError for ResourceNotFoundException
    error_response = {
        "Error": {
            "Code": "ResourceNotFoundException",
            "Message": "Project not found"
        }
    }
    client_error = action.client.exceptions.ClientError(error_response, "ListWebhooksForProject")
    action.client.list_webhooks_for_project.side_effect = client_error
    
    resources = ["non-existent-project"]
    result = await action._execute(resources)
    
    assert len(result) == 1
    webhook_data = result[0]
    assert webhook_data["webhook"] == []


@pytest.mark.asyncio
async def test_get_project_webhooks_action_empty_resources():
    """Test the GetProjectWebhooksAction with empty resources list."""
    action = GetProjectWebhooksAction(AsyncMock())

    result = await action._execute([])
    
    assert result == []
    action.client.list_webhooks_for_project.assert_not_called()