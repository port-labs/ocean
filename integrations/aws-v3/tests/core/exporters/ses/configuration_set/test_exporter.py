from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.ses.configuration_set.exporter import (
    SesConfigurationSetExporter,
)
from aws.core.exporters.ses.configuration_set.models import (
    SingleConfigurationSetRequest,
    PaginatedConfigurationSetRequest,
)
from aws.core.exporters.ses.regions import SES_SUPPORTED_REGIONS


class TestSesConfigurationSetExporter:
    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> SesConfigurationSetExporter:
        return SesConfigurationSetExporter(mock_session)

    def test_service_name(self, exporter: SesConfigurationSetExporter) -> None:
        assert exporter._service_name == "sesv2"

    def test_supported_regions(self, exporter: SesConfigurationSetExporter) -> None:
        assert exporter._supported_regions == SES_SUPPORTED_REGIONS
        assert "us-east-1" in exporter._supported_regions
        assert "ap-southeast-4" not in exporter._supported_regions

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = SesConfigurationSetExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ses.configuration_set.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ses.configuration_set.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesConfigurationSetExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_configuration_set.return_value = {
            "ConfigurationSetName": "my-config-set",
        }

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_config_set_data = {
            "ConfigurationSetName": "my-config-set",
            "SendingOptions": {"SendingEnabled": True},
            "ReputationOptions": {"ReputationMetricsEnabled": True},
        }
        mock_inspector.inspect.return_value = [mock_config_set_data]

        # Create request
        request = SingleConfigurationSetRequest(
            configuration_set_name="my-config-set",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute
        result = await exporter.get_resource(request)

        # Verify
        assert isinstance(result, dict)
        assert result["ConfigurationSetName"] == "my-config-set"

        mock_client.get_configuration_set.assert_awaited_once_with(
            ConfigurationSetName="my-config-set"
        )
        mock_inspector.inspect.assert_called_once()
        assert mock_inspector.inspect.call_args.args[0] == [
            {"ConfigurationSetName": "my-config-set"}
        ]

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ses.configuration_set.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ses.configuration_set.exporter.ResourceInspector")
    async def test_get_resource_configuration_set_not_found(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesConfigurationSetExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_configuration_set.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "gone"}},
            "GetConfigurationSet",
        )

        request = SingleConfigurationSetRequest(
            configuration_set_name="my-config-set",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        with pytest.raises(ClientError) as exc_info:
            await exporter.get_resource(request)

        assert exc_info.value.response["Error"]["Code"] == "NotFoundException"
        mock_inspector_class.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ses.configuration_set.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ses.configuration_set.exporter.ResourceInspector")
    async def test_get_resource_empty_result(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesConfigurationSetExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_configuration_set.return_value = {
            "ConfigurationSetName": "nonexistent-set",
        }

        # Inspector returns empty
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        # Create request
        request = SingleConfigurationSetRequest(
            configuration_set_name="nonexistent-set",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute
        result = await exporter.get_resource(request)

        assert result == {}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ses.configuration_set.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ses.configuration_set.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesConfigurationSetExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock list_configuration_sets
        mock_client.list_configuration_sets.return_value = {
            "ConfigurationSets": ["my-config-set", "another-config-set"]
        }

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_config_set_data = [
            {
                "ConfigurationSetName": "my-config-set",
                "SendingOptions": {"SendingEnabled": True},
            },
            {
                "ConfigurationSetName": "another-config-set",
                "SendingOptions": {"SendingEnabled": False},
            },
        ]
        mock_inspector.inspect.return_value = mock_config_set_data

        # Create request
        request = PaginatedConfigurationSetRequest(
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute
        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        # Verify
        assert len(results) == 2
        assert results[0]["ConfigurationSetName"] == "my-config-set"
        assert results[1]["ConfigurationSetName"] == "another-config-set"

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ses.configuration_set.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ses.configuration_set.exporter.ResourceInspector")
    async def test_get_paginated_resources_follows_next_token(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesConfigurationSetExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # list_configuration_sets paginates via NextToken
        mock_client.list_configuration_sets.side_effect = [
            {
                "ConfigurationSets": ["first-set"],
                "NextToken": "page-2",
            },
            {
                "ConfigurationSets": ["second-set"],
            },
        ]

        # Inspector passes through
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = lambda config_sets, *a, **kw: config_sets

        # Create request
        request = PaginatedConfigurationSetRequest(
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute
        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        # Verify
        assert len(results) == 2
        assert results[0]["ConfigurationSetName"] == "first-set"
        assert results[1]["ConfigurationSetName"] == "second-set"
        assert mock_client.list_configuration_sets.call_count == 2
        mock_client.list_configuration_sets.assert_any_call()
        mock_client.list_configuration_sets.assert_any_call(NextToken="page-2")

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ses.configuration_set.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ses.configuration_set.exporter.ResourceInspector")
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesConfigurationSetExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock list_configuration_sets returning no sets
        mock_client.list_configuration_sets.return_value = {"ConfigurationSets": []}

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        # Create request
        request = PaginatedConfigurationSetRequest(
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute
        results = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        # Verify
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("aws.core.exporters.ses.configuration_set.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.ses.configuration_set.exporter.ResourceInspector")
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesConfigurationSetExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Inspector raises exception
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Inspector error")

        # Create request
        request = SingleConfigurationSetRequest(
            configuration_set_name="my-config-set",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute and verify exception is raised
        with pytest.raises(Exception, match="Inspector error"):
            await exporter.get_resource(request)
