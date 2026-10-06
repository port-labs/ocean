from typing import Any
from unittest.mock import AsyncMock, call
import pytest

from aws.core.exporters.codedeploy.application.actions import (
    GetCodeDeployApplicationDetailsAction,
    GetCodeDeployApplicationTagsAction,
    CodeDeployApplicationActionInput,
)


class TestGetCodeDeployApplicationDetailsAction:
    @pytest.fixture
    def action(
        self,
    ) -> GetCodeDeployApplicationDetailsAction:
        """Create a GetCodeDeployApplicationDetailsAction instance for testing."""
        return GetCodeDeployApplicationDetailsAction(AsyncMock())

    @pytest.mark.asyncio
    async def test_execute_success(
        self, action: GetCodeDeployApplicationDetailsAction
    ) -> None:
        # Arrange
        resources = CodeDeployApplicationActionInput(
            items=["a", "b"],
            region="region",
            account_id="account_id",
        )
        mock_response_one = {"applicationName": "b"}
        mock_response_two = {"applicationName": "a"}
        action.client.batch_get_applications.return_value = {
            "applicationsInfo": [mock_response_one, mock_response_two]
        }

        # Act
        result = await action._execute(resources)

        # Assert
        assert result == [mock_response_two, mock_response_one]
        action.client.batch_get_applications.assert_called_once_with(
            applicationNames=resources.items
        )

    @pytest.mark.asyncio
    async def test_execute_empty_applications_info(
        self, action: GetCodeDeployApplicationDetailsAction
    ) -> None:
        # Arrange
        resources = CodeDeployApplicationActionInput(
            items=["a", "b"],
            region="region",
            account_id="account_id",
        )
        action.client.batch_get_applications.return_value = {}

        # Act
        result = await action._execute(resources)

        # Assert
        assert result == []
        action.client.batch_get_applications.assert_called_once_with(
            applicationNames=resources.items
        )


class TestGetCodeDeployApplicationTagsAction:
    @pytest.fixture
    def action(self) -> GetCodeDeployApplicationTagsAction:
        """Create a GetCodeDeployApplicationTagsAction instance for testing."""
        return GetCodeDeployApplicationTagsAction(AsyncMock())

    @pytest.mark.asyncio
    async def test_execute_success(
        self, action: GetCodeDeployApplicationTagsAction
    ) -> None:
        # Arrange
        resources = CodeDeployApplicationActionInput(
            items=["a", "b", "c"],
            region="region",
            account_id="account_id",
        )

        tag_one = {"Tags": [{"Key": "Environment", "Value": "production"}]}
        tag_two = {"Tags": [{"Key": "Environment", "Value": "staging"}]}

        def mock_list_tags(ResourceArn: str, **kwargs: Any) -> dict[str, Any]:
            if ResourceArn.endswith(resources.items[0]):
                return tag_one
            elif ResourceArn.endswith(resources.items[1]):
                return tag_two
            raise Exception

        action.client.list_tags_for_resource.side_effect = mock_list_tags

        # Act
        result = await action._execute(resources)

        # Assert
        assert result == [
            tag_one,
            tag_two,
            {},
        ]

        action.client.list_tags_for_resource.assert_has_calls(
            calls=[
                call(
                    ResourceArn=f"arn:aws:codedeploy:{resources.region}:{resources.account_id}:application:{name}"
                )
                for name in resources.items
            ]
        )
