import pytest
from unittest.mock import AsyncMock
from aws.core.exporters.ecs.task_definition.actions import (
    ListTaskDefinitionsAction,
    DescribeTaskDefinitionsAction,
    EcsTaskDefinitionActionsMap,
)


class TestListTaskDefinitionsAction:

    @pytest.mark.asyncio
    async def test_execute_returns_arn_dicts(self) -> None:
        mock_client = AsyncMock()
        action = ListTaskDefinitionsAction(mock_client)
        arns = [
            "arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1",
            "arn:aws:ecs:us-east-1:123456789012:task-definition/task2:3",
        ]

        result = await action._execute(arns)

        assert len(result) == 2
        assert result[0] == {
            "TaskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1"
        }
        assert result[1] == {
            "TaskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/task2:3"
        }

    @pytest.mark.asyncio
    async def test_execute_empty_list(self) -> None:
        mock_client = AsyncMock()
        action = ListTaskDefinitionsAction(mock_client)

        result = await action._execute([])

        assert result == []


class TestDescribeTaskDefinitionsAction:

    @pytest.mark.asyncio
    async def test_execute_with_single_arn(self) -> None:
        mock_client = AsyncMock()
        mock_client.describe_task_definition.return_value = {
            "taskDefinition": {
                "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1",
                "family": "task1",
                "revision": 1,
                "status": "ACTIVE",
                "containerDefinitions": [{"name": "web", "image": "nginx:latest"}],
            },
            "tags": [{"key": "env", "value": "prod"}],
        }

        action = DescribeTaskDefinitionsAction(mock_client)
        arns = ["arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1"]

        result = await action._execute(arns)

        assert len(result) == 1
        assert result[0]["family"] == "task1"
        assert result[0]["Tags"] == [{"key": "env", "value": "prod"}]

        mock_client.describe_task_definition.assert_called_once_with(
            taskDefinition="arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1",
            include=["TAGS"],
        )

    @pytest.mark.asyncio
    async def test_execute_with_multiple_arns(self) -> None:
        mock_client = AsyncMock()

        async def mock_describe(taskDefinition: str, include: list[str]) -> dict:  # type: ignore[type-arg]
            family = taskDefinition.split("/")[-1].split(":")[0]
            return {
                "taskDefinition": {
                    "taskDefinitionArn": taskDefinition,
                    "family": family,
                    "revision": 1,
                    "status": "ACTIVE",
                },
                "tags": [],
            }

        mock_client.describe_task_definition.side_effect = mock_describe

        action = DescribeTaskDefinitionsAction(mock_client)
        arns = [
            "arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1",
            "arn:aws:ecs:us-east-1:123456789012:task-definition/task2:2",
        ]

        result = await action._execute(arns)

        assert len(result) == 2
        assert result[0]["family"] == "task1"
        assert result[1]["family"] == "task2"
        assert mock_client.describe_task_definition.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_merges_tags_into_task_definition(self) -> None:
        mock_client = AsyncMock()
        mock_client.describe_task_definition.return_value = {
            "taskDefinition": {
                "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1",
                "family": "task1",
            },
            "tags": [
                {"key": "team", "value": "platform"},
                {"key": "service", "value": "api"},
            ],
        }

        action = DescribeTaskDefinitionsAction(mock_client)
        result = await action._execute(
            ["arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1"]
        )

        assert result[0]["Tags"] == [
            {"key": "team", "value": "platform"},
            {"key": "service", "value": "api"},
        ]

    @pytest.mark.asyncio
    async def test_execute_handles_missing_tags(self) -> None:
        mock_client = AsyncMock()
        mock_client.describe_task_definition.return_value = {
            "taskDefinition": {
                "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1",
                "family": "task1",
            },
        }

        action = DescribeTaskDefinitionsAction(mock_client)
        result = await action._execute(
            ["arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1"]
        )

        assert result[0]["Tags"] == []


class TestEcsTaskDefinitionActionsMap:

    def test_defaults(self) -> None:
        action_map = EcsTaskDefinitionActionsMap()
        assert len(action_map.defaults) == 2
        assert ListTaskDefinitionsAction in action_map.defaults
        assert DescribeTaskDefinitionsAction in action_map.defaults

    def test_options_empty(self) -> None:
        action_map = EcsTaskDefinitionActionsMap()
        assert action_map.options == []

    def test_merge_with_no_include(self) -> None:
        action_map = EcsTaskDefinitionActionsMap()
        merged = action_map.merge([])
        assert len(merged) == 2
        assert ListTaskDefinitionsAction in merged
        assert DescribeTaskDefinitionsAction in merged
