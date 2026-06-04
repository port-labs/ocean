import botocore.exceptions
import pytest
from unittest.mock import AsyncMock, MagicMock
from aws.core.exporters.codebuild.project.actions import (
    ListProjectsAction,
    GetProjectDetailsAction,
)


@pytest.mark.asyncio
async def test_list_projects_action() -> None:
    # Arrange
    action = ListProjectsAction(MagicMock())
    projects = ["project1", "project2", "project3"]

    # Act
    result = await action._execute(projects)

    # Assert
    assert result == [
        {"name": "project1", "id": "project1"},
        {"name": "project2", "id": "project2"},
        {"name": "project3", "id": "project3"},
    ]


@pytest.mark.asyncio
async def test_get_project_details_action() -> None:
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
                    "location": "https://github.com/example/repo.git",
                },
                "environment": {
                    "type": "LINUX_CONTAINER",
                    "image": "aws/codebuild/amazonlinux2-x86_64-standard:3.0",
                    "computeType": "BUILD_GENERAL1_MEDIUM",
                },
                "artifacts": {"type": "NO_ARTIFACTS"},
                "tags": [],
            }
        ]
    }

    action.client.batch_get_projects.return_value = mock_response

    resources = ["test-project"]
    result = await action._execute(resources)

    assert len(result) == 1
    project = result[0]
    assert project["name"] == "test-project"
    assert (
        project["arn"]
        == "arn:aws:codebuild:us-east-1:123456789012:project/test-project"
    )
    assert project["description"] == "Test project description"
    assert (
        project["serviceRole"]
        == "arn:aws:iam::123456789012:role/service-role/codebuild-test-service-role"
    )
    assert project["timeoutInMinutes"] == 60


@pytest.mark.asyncio
async def test_get_project_details_action_empty_resources() -> None:
    action = GetProjectDetailsAction(AsyncMock())

    result = await action._execute([])

    assert result == []
    action.client.batch_get_projects.assert_not_called()
