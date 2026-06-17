from unittest.mock import AsyncMock, call
import pytest

from aws.core.exporters.codepipeline.pipeline.actions import (
    GetPipelineDetailsAction,
    GetPipelineTagsAction,
    ListPipelinesAction,
    CodePipelinePipelineActionInput,
)


class TestGetPipelineDetailsAction:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        # Arrange
        action = GetPipelineDetailsAction(AsyncMock())
        data = CodePipelinePipelineActionInput(
            items=[
                {"name": "pipeline-1"},
                {"name": "pipeline-2"},
                {"bad_data": "pipeline-3"},
            ],
            region="region",
            account_id="account_id",
        )

        action.client.get_pipeline.side_effect = lambda name, **kwargs: {
            "pipeline": {
                "name": name,
            },
            "metadata": {
                "someKey": "some-value",
            },
        }

        # Act
        result = await action.execute(data)

        # Assert
        assert result == [
            {"name": data.items[0]["name"], "someKey": "some-value"},
            {"name": data.items[1]["name"], "someKey": "some-value"},
            {},
        ]


class TestGetPipelineTagsAction:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        # Arrange
        action = GetPipelineTagsAction(AsyncMock())
        data = CodePipelinePipelineActionInput(
            items=[
                {"name": "pipeline-1"},
                {"name": "pipeline-2"},
                {"bad_data": "pipeline-3"},
            ],
            region="region",
            account_id="account_id",
        )

        tag_one = {"Tags": [{"key": "Environment", "value": "production"}]}
        tag_two = {
            "Tags": [
                {"key": "Environment", "value": "staging"},
            ]
        }

        action.client.get_pipeline.side_effect = lambda name, **kwargs: {
            "metadata": {
                "pipelineArn": f"prefix:{name}",
            }
        }
        action.client.list_tags_for_resource.side_effect = lambda resourceArn: (
            tag_one if resourceArn.endswith("pipeline-1") else tag_two
        )

        # Act
        result = await action.execute(data)

        # Assert
        assert result == [tag_one, tag_two, {}]

        action.client.get_pipeline.assert_has_calls(
            [
                call(name=data.items[0]["name"]),
                call(name=data.items[1]["name"]),
            ]
        )
        action.client.list_tags_for_resource.assert_has_calls(
            [
                call(resourceArn=f"prefix:{data.items[0]['name']}"),
                call(resourceArn=f"prefix:{data.items[1]['name']}"),
            ]
        )


class TestListPipelinesAction:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        # Arrange
        action = ListPipelinesAction(AsyncMock())
        data = CodePipelinePipelineActionInput(
            items=[
                {"name": "pipeline-1"},
                {"name": "pipeline-2"},
                {"bad_data": "pipeline-3"},
            ],
            region="region",
            account_id="account_id",
        )

        # Act
        result = await action.execute(data)

        # Assert
        assert result == data.items
