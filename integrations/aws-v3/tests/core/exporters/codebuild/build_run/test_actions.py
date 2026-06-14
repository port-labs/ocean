import pytest
from unittest.mock import AsyncMock, MagicMock
from aws.core.exporters.codebuild.build_run.actions import (
    GetBuildDetailsAction,
    ListBuildsAction,
)


@pytest.mark.asyncio
async def test_get_build_details_action() -> None:
    # Arrange
    action = GetBuildDetailsAction(AsyncMock())

    mock_response = {"builds": [MagicMock()]}

    action.client.batch_get_builds.return_value = mock_response

    resources = [MagicMock()]

    # Act
    result = await action._execute(resources)

    # Assert
    assert len(result) == 1
    assert result[0] == mock_response['builds'][0]
    action.client.batch_get_builds.assert_called_once_with(ids=resources)


@pytest.mark.asyncio
async def test_list_builds_action() -> None:
    # Arrange
    action = ListBuildsAction(AsyncMock())

    resources = [
        MagicMock(),
        MagicMock(),
    ]

    # Act
    result = await action._execute(resources)

    # Assert
    assert result == [{"id": resources[0]}, {"id": resources[1]}, ]
