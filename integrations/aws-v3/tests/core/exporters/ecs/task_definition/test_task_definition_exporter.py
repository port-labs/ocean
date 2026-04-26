import pytest
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from aws.core.exporters.ecs.task_definition.exporter import EcsTaskDefinitionExporter
from aws.core.exporters.ecs.task_definition.models import (
    SingleTaskDefinitionRequest,
    PaginatedTaskDefinitionRequest,
)


class TestEcsTaskDefinitionExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> EcsTaskDefinitionExporter:
        return EcsTaskDefinitionExporter(mock_session)

    def test_service_name(self, exporter: EcsTaskDefinitionExporter) -> None:
        assert exporter._service_name == "ecs"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = EcsTaskDefinitionExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._service_name == "ecs"

    @pytest.mark.asyncio
    async def test_get_resource_single_task_definition(
        self, exporter: EcsTaskDefinitionExporter
    ) -> None:
        options = SingleTaskDefinitionRequest(
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/my-task:1",
            region="us-east-1",
            account_id="123456789012",
        )

        mock_task_def_data = {
            "TaskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/my-task:1",
            "Family": "my-task",
            "Revision": 1,
            "Status": "ACTIVE",
        }

        with patch(
            "aws.core.exporters.ecs.task_definition.exporter.AioBaseClientProxy"
        ) as mock_proxy_class:
            mock_proxy = AsyncMock()
            mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

            mock_inspector = AsyncMock()
            mock_inspector.inspect.return_value = [mock_task_def_data]

            with patch(
                "aws.core.exporters.ecs.task_definition.exporter.ResourceInspector",
                return_value=mock_inspector,
            ):
                result = await exporter.get_resource(options)

        assert result == mock_task_def_data
        mock_inspector.inspect.assert_called_once()

        call_args = mock_inspector.inspect.call_args[0][0]
        assert len(call_args) == 1
        assert (
            call_args[0]
            == "arn:aws:ecs:us-east-1:123456789012:task-definition/my-task:1"
        )

        extra_context = mock_inspector.inspect.call_args[1]["extra_context"]
        assert extra_context["AccountId"] == "123456789012"
        assert extra_context["Region"] == "us-east-1"

    @pytest.mark.asyncio
    async def test_get_resource_empty_response(
        self, exporter: EcsTaskDefinitionExporter
    ) -> None:
        options = SingleTaskDefinitionRequest(
            task_definition_arn="arn:aws:ecs:us-east-1:123456789012:task-definition/nonexistent:1",
            region="us-east-1",
            account_id="123456789012",
        )

        with patch(
            "aws.core.exporters.ecs.task_definition.exporter.AioBaseClientProxy"
        ) as mock_proxy_class:
            mock_proxy = AsyncMock()
            mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

            mock_inspector = AsyncMock()
            mock_inspector.inspect.return_value = []

            with patch(
                "aws.core.exporters.ecs.task_definition.exporter.ResourceInspector",
                return_value=mock_inspector,
            ):
                result = await exporter.get_resource(options)

        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.task_definition.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.task_definition.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcsTaskDefinitionExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate(
            status: str = "ACTIVE",
        ) -> AsyncGenerator[list[str], None]:
            yield [
                "arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1",
                "arn:aws:ecs:us-east-1:123456789012:task-definition/task2:3",
            ]

        class MockPaginator:
            def paginate(
                self, status: str = "ACTIVE"
            ) -> AsyncGenerator[list[str], None]:
                return mock_paginate(status)

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_task_def_details = [
            {
                "TaskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1",
                "Family": "task1",
                "Revision": 1,
                "Status": "ACTIVE",
            },
            {
                "TaskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/task2:3",
                "Family": "task2",
                "Revision": 3,
                "Status": "ACTIVE",
            },
        ]

        mock_inspector.inspect.return_value = mock_task_def_details

        options = PaginatedTaskDefinitionRequest(
            region="us-east-1",
            account_id="123456789012",
        )

        results = []
        async for result in exporter.get_paginated_resources(options):
            results.extend(result)

        assert len(results) == 2
        assert results[0]["Family"] == "task1"
        assert results[1]["Family"] == "task2"

        call_args = mock_inspector.inspect.call_args[0][0]
        assert len(call_args) == 2
        assert (
            call_args[0] == "arn:aws:ecs:us-east-1:123456789012:task-definition/task1:1"
        )
        assert (
            call_args[1] == "arn:aws:ecs:us-east-1:123456789012:task-definition/task2:3"
        )

        extra_context = mock_inspector.inspect.call_args[1]["extra_context"]
        assert extra_context["AccountId"] == "123456789012"
        assert extra_context["Region"] == "us-east-1"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecs.task_definition.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecs.task_definition.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty_page(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcsTaskDefinitionExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate(
            status: str = "ACTIVE",
        ) -> AsyncGenerator[list[str], None]:
            yield []

        class MockPaginator:
            def paginate(
                self, status: str = "ACTIVE"
            ) -> AsyncGenerator[list[str], None]:
                return mock_paginate(status)

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        options = PaginatedTaskDefinitionRequest(
            region="us-east-1",
            account_id="123456789012",
        )

        results = []
        async for result in exporter.get_paginated_resources(options):
            results.extend(result)

        assert len(results) == 0
        mock_inspector.inspect.assert_not_called()
