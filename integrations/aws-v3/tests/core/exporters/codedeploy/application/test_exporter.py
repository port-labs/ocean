from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.codedeploy.application.exporter import (
    CodeDeployApplicationExporter,
)
from aws.core.exporters.codedeploy.application.models import (
    SingleCodeDeployApplicationRequest,
    PaginatedCodeDeployApplicationRequest,
    CodeDeployApplication,
    CodeDeployApplicationProperties,
)


class TestCodeDeployApplicationExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AioSession for testing."""
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> CodeDeployApplicationExporter:
        """Create a CodeDeployApplicationExporter instance for testing."""
        return CodeDeployApplicationExporter(mock_session)

    def test_service_name(self, exporter: CodeDeployApplicationExporter) -> None:
        """Test that the service name is correctly set."""
        assert exporter._service_name == "codedeploy"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        """Test that the exporter initializes correctly."""
        exporter = CodeDeployApplicationExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codedeploy.application.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.codedeploy.application.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: CodeDeployApplicationExporter,
    ) -> None:
        """Test successful single resource retrieval."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        application = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(
                ApplicationName="test-app",
                ApplicationId="id-1",
                ComputePlatform="Server",
            )
        )
        mock_inspector.inspect.return_value = [application.dict(exclude_none=True)]

        options = SingleCodeDeployApplicationRequest(
            region="us-east-1",
            account_id="123456789012",
            application_name="test-app",
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result == application.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "codedeploy"
        )
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once()

        # Verify the resources passed to inspect contain the application name
        call_args = mock_inspector.inspect.call_args
        assert call_args[0][0] == [{"ApplicationName": "test-app"}]
        assert call_args[0][1] == []

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codedeploy.application.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.codedeploy.application.exporter.ResourceInspector")
    async def test_get_resource_empty_inspection_returns_empty_dict(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: CodeDeployApplicationExporter,
    ) -> None:
        """When inspector returns nothing, get_resource yields {}."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector.inspect.return_value = []
        mock_inspector_class.return_value = mock_inspector

        options = SingleCodeDeployApplicationRequest(
            region="us-east-1",
            account_id="123456789012",
            application_name="missing-app",
            include=[],
        )

        result = await exporter.get_resource(options)

        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codedeploy.application.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.codedeploy.application.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: CodeDeployApplicationExporter,
    ) -> None:
        """Test successful retrieval of paginated CodeDeploy applications."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # The paginator yields application *name* lists (strings); the exporter
        # is responsible for transforming them into dicts with extra context.
        async def mock_paginate() -> AsyncGenerator[list[str], None]:
            yield ["app-b", "app-a"]
            yield ["app-c"]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[str], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        app_a = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(ApplicationName="app-a")
        )
        app_b = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(ApplicationName="app-b")
        )
        app_c = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(ApplicationName="app-c")
        )

        mock_inspector.inspect.side_effect = [
            [app_a.dict(exclude_none=True), app_b.dict(exclude_none=True)],
            [app_c.dict(exclude_none=True)],
        ]

        options = PaginatedCodeDeployApplicationRequest(
            region="us-east-1",
            account_id="123456789012",
            include=[],
        )

        collected: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            collected.extend(page)

        assert len(collected) == 3
        assert collected[0] == app_a.dict(exclude_none=True)
        assert collected[1] == app_b.dict(exclude_none=True)
        assert collected[2] == app_c.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "codedeploy"
        )
        mock_proxy.get_paginator.assert_called_once_with(
            "list_applications", "applications"
        )
        assert mock_inspector.inspect.call_count == 2

        # Verify the first page sorted applications and built resource dicts with
        # the expected per-resource fields.
        first_call_resources = mock_inspector.inspect.call_args_list[0][0][0]
        assert first_call_resources == [
            {
                "applicationName": "app-a",
                "accountId": "123456789012",
                "region": "us-east-1",
            },
            {
                "applicationName": "app-b",
                "accountId": "123456789012",
                "region": "us-east-1",
            },
        ]

        # Verify extra_context is forwarded on every inspection call
        for call in mock_inspector.inspect.call_args_list:
            call_kwargs = call[1]
            assert call_kwargs["extra_context"]["AccountId"] == "123456789012"
            assert call_kwargs["extra_context"]["Region"] == "us-east-1"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codedeploy.application.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.codedeploy.application.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: CodeDeployApplicationExporter,
    ) -> None:
        """Test handling of empty paginated results."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[str], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[str], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        options = PaginatedCodeDeployApplicationRequest(
            region="us-west-1",
            account_id="123456789012",
            include=[],
        )

        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert results == []
        mock_proxy.get_paginator.assert_called_once_with(
            "list_applications", "applications"
        )
        mock_inspector.inspect.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.codedeploy.application.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.codedeploy.application.exporter.ResourceInspector")
    async def test_context_manager_cleanup(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: CodeDeployApplicationExporter,
    ) -> None:
        """Test that context manager properly cleans up resources."""
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_proxy_class.return_value.__aexit__ = AsyncMock()

        mock_inspector = AsyncMock()
        application = CodeDeployApplication(
            Properties=CodeDeployApplicationProperties(ApplicationName="cleanup-test")
        )
        mock_inspector.inspect.return_value = [application.dict(exclude_none=True)]
        mock_inspector_class.return_value = mock_inspector

        options = SingleCodeDeployApplicationRequest(
            region="us-west-2",
            account_id="123456789012",
            application_name="cleanup-test",
            include=[],
        )

        result = await exporter.get_resource(options)
        assert result["Properties"]["ApplicationName"] == "cleanup-test"
        assert result["Type"] == "AWS::CodeDeploy::Application"

        mock_inspector.inspect.assert_called_once()

        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-west-2", "codedeploy"
        )
        mock_proxy_class.return_value.__aenter__.assert_called_once()
        mock_proxy_class.return_value.__aexit__.assert_called_once()
