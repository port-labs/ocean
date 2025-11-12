from typing import AsyncGenerator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ecr.repository.exporter import EcrRepositoryExporter
from aws.core.exporters.ecr.repository.models import (
    SingleRepositoryRequest,
    PaginatedRepositoryRequest,
    Repository,
    RepositoryProperties,
)


class TestEcrRepositoryExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> EcrRepositoryExporter:
        return EcrRepositoryExporter(mock_session)

    def test_service_name(self, exporter: EcrRepositoryExporter) -> None:
        assert exporter._service_name == "ecr"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = EcrRepositoryExporter(mock_session)
        assert exporter.session == mock_session

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecr.repository.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecr.repository.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcrRepositoryExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        repository = Repository(
            Properties=RepositoryProperties(
                RepositoryName="my-repo",
                RepositoryArn="arn:aws:ecr:us-east-1:123456789012:repository/my-repo",
            )
        )
        mock_inspector.inspect.return_value = [repository.dict(exclude_none=True)]

        mock_client.describe_repositories.return_value = {
            "repositories": [
                {
                    "repositoryName": "my-repo",
                    "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/my-repo",
                }
            ]
        }

        options = SingleRepositoryRequest(
            region="us-west-2",
            account_id="123456789012",
            repository_name="my-repo",
            include=["GetRepositoryPolicyAction"],
        )

        result = await exporter.get_resource(options)

        assert result == repository.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(exporter.session, "us-west-2", "ecr")
        mock_client.describe_repositories.assert_called_once_with(
            repositoryNames=["my-repo"]
        )
        mock_inspector.inspect.assert_called_once_with(
            [
                {
                    "repositoryName": "my-repo",
                    "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/my-repo",
                }
            ],
            ["GetRepositoryPolicyAction"],
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecr.repository.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecr.repository.exporter.ResourceInspector")
    async def test_get_resource_not_found(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcrRepositoryExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.describe_repositories.return_value = {"repositories": []}

        options = SingleRepositoryRequest(
            region="us-east-1",
            account_id="123456789012",
            repository_name="nonexistent",
            include=[],
        )

        result = await exporter.get_resource(options)
        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecr.repository.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecr.repository.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcrRepositoryExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {
                    "repositoryName": "repo1",
                    "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/repo1",
                },
                {
                    "repositoryName": "repo2",
                    "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/repo2",
                },
            ]
            yield [
                {
                    "repositoryName": "repo3",
                    "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/repo3",
                }
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        repo1 = Repository(Properties=RepositoryProperties(RepositoryName="repo1"))
        repo2 = Repository(Properties=RepositoryProperties(RepositoryName="repo2"))
        repo3 = Repository(Properties=RepositoryProperties(RepositoryName="repo3"))

        mock_inspector.inspect.side_effect = [
            [repo1.dict(exclude_none=True), repo2.dict(exclude_none=True)],
            [repo3.dict(exclude_none=True)],
        ]

        options = PaginatedRepositoryRequest(
            region="us-east-1",
            account_id="123456789012",
            include=["GetRepositoryPolicyAction"],
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == repo1.dict(exclude_none=True)
        assert collected[1] == repo2.dict(exclude_none=True)
        assert collected[2] == repo3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(exporter.session, "us-east-1", "ecr")
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_repositories", "repositories"
        )
        assert mock_inspector.inspect.call_count == 2

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ecr.repository.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ecr.repository.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: EcrRepositoryExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        options = PaginatedRepositoryRequest(
            region="us-west-1",
            account_id="123456789012",
            include=[],
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with(
            "describe_repositories", "repositories"
        )
        mock_inspector.inspect.assert_not_called()
