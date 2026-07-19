import pytest
from pydantic import ValidationError
from datetime import datetime

from aws.core.exporters.ecs.task_definition.models import (
    TaskDefinition,
    TaskDefinitionProperties,
    SingleTaskDefinitionRequest,
    PaginatedTaskDefinitionRequest,
)


class TestSingleTaskDefinitionRequest:

    def test_initialization_with_required_fields(self) -> None:
        options = SingleTaskDefinitionRequest(
            region="us-east-1",
            account_id="123456789012",
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/my-task:1",
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert (
            options.task_definition_arn
            == "arn:aws:ecs:us-east-1:123456789012:task-definition/my-task:1"
        )
        assert options.include == []

    def test_initialization_with_all_fields(self) -> None:
        include_list = ["DescribeTaskDefinitionsAction"]
        options = SingleTaskDefinitionRequest(
            region="eu-west-1",
            account_id="123456789012",
            task_definition_arn="arn:aws:ecs:eu-west-1:123456789012:task-definition/my-task:2",
            include=include_list,
        )
        assert options.region == "eu-west-1"
        assert options.include == include_list

    def test_missing_required_region(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleTaskDefinitionRequest(
                account_id="123456789012",
                task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/my-task:1",
            )  # type: ignore
        assert "region" in str(exc_info.value)

    def test_missing_required_task_definition_arn(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            SingleTaskDefinitionRequest(
                region="us-east-1", account_id="123456789012"
            )  # type: ignore
        assert "task_definition_arn" in str(exc_info.value)


class TestPaginatedTaskDefinitionRequest:

    def test_inheritance(self) -> None:
        options = PaginatedTaskDefinitionRequest(
            region="us-west-2", account_id="123456789012"
        )
        assert isinstance(options, PaginatedTaskDefinitionRequest)

    def test_initialization_with_required_fields(self) -> None:
        options = PaginatedTaskDefinitionRequest(
            region="us-east-1", account_id="123456789012"
        )
        assert options.region == "us-east-1"
        assert options.account_id == "123456789012"
        assert options.include == []

    def test_initialization_with_include(self) -> None:
        include_list = ["DescribeTaskDefinitionsAction"]
        options = PaginatedTaskDefinitionRequest(
            region="ap-southeast-1", account_id="123456789012", include=include_list
        )
        assert options.include == include_list


class TestTaskDefinitionProperties:

    def test_initialization_empty(self) -> None:
        properties = TaskDefinitionProperties()
        assert properties.taskDefinitionArn == ""
        assert properties.family == ""
        assert properties.revision == 0
        assert properties.status is None
        assert properties.containerDefinitions == []
        assert properties.cpu is None
        assert properties.memory is None
        assert properties.networkMode is None
        assert properties.requiresCompatibilities == []
        assert properties.taskRoleArn is None
        assert properties.executionRoleArn is None
        assert properties.volumes == []
        assert properties.placementConstraints == []
        assert properties.tags == []
        assert properties.registeredAt is None

    def test_initialization_with_properties(self) -> None:
        properties = TaskDefinitionProperties(
            taskDefinitionArn="arn:aws:ecs:us-east-1:123456789012:task-definition/my-task:1",
            family="my-task",
            revision=1,
            status="ACTIVE",
            cpu="256",
            memory="512",
            networkMode="awsvpc",
            requiresCompatibilities=["FARGATE"],
            containerDefinitions=[
                {"name": "web", "image": "nginx:latest", "cpu": 256, "memory": 512}
            ],
            tags=[{"key": "env", "value": "prod"}],
        )
        assert (
            properties.taskDefinitionArn
            == "arn:aws:ecs:us-east-1:123456789012:task-definition/my-task:1"
        )
        assert properties.family == "my-task"
        assert properties.revision == 1
        assert properties.status == "ACTIVE"
        assert properties.cpu == "256"
        assert properties.memory == "512"
        assert properties.networkMode == "awsvpc"
        assert properties.requiresCompatibilities == ["FARGATE"]
        assert len(properties.containerDefinitions) == 1
        assert properties.containerDefinitions[0]["image"] == "nginx:latest"

    def test_aliases_work_correctly(self) -> None:
        properties = TaskDefinitionProperties(
            taskDefinitionArn="arn:test",
            family="test-family",
            revision=5,
            taskRoleArn="arn:aws:iam::123456789012:role/task-role",
            executionRoleArn="arn:aws:iam::123456789012:role/exec-role",
        )

        result = properties.dict(by_alias=True)
        assert "TaskDefinitionArn" in result
        assert "Family" in result
        assert "Revision" in result
        assert "TaskRoleArn" in result
        assert "ExecutionRoleArn" in result

    def test_extra_fields_ignored(self) -> None:
        properties = TaskDefinitionProperties(
            taskDefinitionArn="arn:test",
            family="test",
            unknownField="should-be-ignored",  # type: ignore[call-arg]
        )
        assert not hasattr(properties, "unknownField")

    def test_registered_at_datetime(self) -> None:
        dt = datetime(2024, 6, 15, 10, 30, 0)
        properties = TaskDefinitionProperties(registeredAt=dt)
        assert properties.registeredAt == dt


class TestTaskDefinition:

    def test_type_is_fixed(self) -> None:
        td = TaskDefinition(Properties=TaskDefinitionProperties(family="task1"))
        assert td.Type == "AWS::ECS::TaskDefinition"

    def test_initialization_with_properties(self) -> None:
        properties = TaskDefinitionProperties(
            taskDefinitionArn="arn:aws:ecs:us-east-1:123456789012:task-definition/my-task:1",
            family="my-task",
            revision=1,
            cpu="512",
            memory="1024",
        )
        td = TaskDefinition(Properties=properties)
        assert td.Properties == properties
        assert td.Properties.family == "my-task"
        assert td.Properties.cpu == "512"

    def test_dict_exclude_none(self) -> None:
        td = TaskDefinition(Properties=TaskDefinitionProperties(family="my-task"))
        data = td.dict(exclude_none=True)
        assert data["Type"] == "AWS::ECS::TaskDefinition"
        assert data["Properties"]["family"] == "my-task"

    def test_properties_default_factory(self) -> None:
        td1 = TaskDefinition(Properties=TaskDefinitionProperties(family="task1"))
        td2 = TaskDefinition(Properties=TaskDefinitionProperties(family="task2"))
        assert td1.Properties is not td2.Properties
        assert td1.Properties.family == "task1"
        assert td2.Properties.family == "task2"
