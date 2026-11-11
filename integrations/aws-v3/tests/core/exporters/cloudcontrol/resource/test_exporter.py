from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.cloudcontrol.resource.actions import (
    CloudControlActionInput,
    CloudControlResourceIdentifier,
)
from aws.core.exporters.cloudcontrol.resource.exporter import CloudControlExporter
from aws.core.exporters.cloudcontrol.resource.models import (
    CloudControlResource,
    PaginatedCloudControlResourceRequest,
    SingleCloudControlResourceRequest,
)
from aws.core.modeling.resource_inspector import ResourceInspector


def _paginator_with(
    pages: AsyncGenerator[list[dict[str, Any]], None] | None = None,
    *,
    error: Exception | None = None,
) -> MagicMock:
    async def mock_paginate(
        **kwargs: Any,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if error is not None:
            raise error
            yield []  # pragma: no cover
        assert pages is not None
        async for page in pages:
            yield page

    paginator = MagicMock()
    paginator.paginate = mock_paginate
    return paginator


class TestCloudControlExporter:
    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> CloudControlExporter:
        return CloudControlExporter(mock_session)

    def test_service_name(self, exporter: CloudControlExporter) -> None:
        assert exporter._service_name == "cloudcontrol"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = CloudControlExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: CloudControlExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_resource.return_value = {
            "ResourceDescription": {
                "Identifier": "admin-role",
                "Properties": '{"RoleName": "admin-role"}',
            }
        }

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = [
            {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "Identifier": "admin-role",
                    "RoleName": "admin-role",
                },
            }
        ]

        request = SingleCloudControlResourceRequest(
            region="us-east-1",
            account_id="123456789012",
            type_name="AWS::IAM::Role",
            identifier="admin-role",
        )
        result = await exporter.get_resource(request)

        assert result["Type"] == "AWS::IAM::Role"
        mock_client.get_resource.assert_awaited_once_with(
            TypeName="AWS::IAM::Role", Identifier="admin-role"
        )
        inspect_input = mock_inspector.inspect.await_args.args[0]
        assert isinstance(inspect_input, CloudControlActionInput)
        assert inspect_input.type_name == "AWS::IAM::Role"
        assert inspect_input.items[0].identifier == "admin-role"
        assert inspect_input.items[0].properties == {"RoleName": "admin-role"}

    @pytest.mark.asyncio
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.ResourceInspector")
    async def test_get_resource_not_found(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: CloudControlExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy
        mock_client.get_resource.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "gone",
                }
            },
            "GetResource",
        )

        request = SingleCloudControlResourceRequest(
            region="us-east-1",
            account_id="123456789012",
            type_name="AWS::IAM::Role",
            identifier="missing",
        )
        with pytest.raises(ClientError) as exc_info:
            await exporter.get_resource(request)

        assert exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"
        mock_inspector_class.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: CloudControlExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_pages() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "Identifier": "role-1",
                    "Properties": '{"RoleName": "role-1"}',
                },
                {
                    "Identifier": "role-2",
                    "Properties": '{"RoleName": "role-2"}',
                },
            ]

        mock_proxy.get_paginator = MagicMock(return_value=_paginator_with(mock_pages()))

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = [
            {"Type": "AWS::IAM::Role", "Properties": {"Identifier": "role-1"}},
            {"Type": "AWS::IAM::Role", "Properties": {"Identifier": "role-2"}},
        ]

        request = PaginatedCloudControlResourceRequest(
            region="us-east-1",
            account_id="123456789012",
            type_name="AWS::IAM::Role",
        )
        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        assert len(results) == 2
        mock_proxy.get_paginator.assert_called_once_with(
            "list_resources", "ResourceDescriptions"
        )
        inspect_input = mock_inspector.inspect.await_args.args[0]
        assert [item.identifier for item in inspect_input.items] == ["role-1", "role-2"]
        assert mock_inspector.inspect.await_args.args[1] == []

    @pytest.mark.asyncio
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.ResourceInspector")
    async def test_get_paginated_resources_uses_get_resource_action(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: CloudControlExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_pages() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [{"Identifier": "role-1", "Properties": "{}"}]

        mock_proxy.get_paginator = MagicMock(return_value=_paginator_with(mock_pages()))
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = [{"Type": "AWS::IAM::Role"}]

        request = PaginatedCloudControlResourceRequest(
            region="us-east-1",
            account_id="123456789012",
            type_name="AWS::IAM::Role",
            use_get_resource_api=True,
        )
        async for _ in exporter.get_paginated_resources(request):
            pass

        assert mock_inspector.inspect.await_args.args[1] == ["GetResourceAction"]

    @pytest.mark.asyncio
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.ResourceInspector")
    async def test_get_paginated_resources_skips_unsupported_type(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: CloudControlExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_proxy.get_paginator = MagicMock(
            return_value=_paginator_with(
                error=ClientError(
                    {
                        "Error": {
                            "Code": "TypeNotFoundException",
                            "Message": "Type not found",
                        }
                    },
                    "ListResources",
                )
            )
        )

        request = PaginatedCloudControlResourceRequest(
            region="us-east-1",
            account_id="123456789012",
            type_name="AWS::DoesNot::Exist",
        )
        results: list[dict[str, Any]] = []
        async for page in exporter.get_paginated_resources(request):
            results.extend(page)

        assert results == []
        mock_inspector_class.return_value.inspect.assert_not_called()

    @pytest.mark.asyncio
    @patch("aws.core.exporters.cloudcontrol.resource.exporter.AioBaseClientProxy")
    async def test_get_paginated_resources_reraises_other_errors(
        self,
        mock_proxy_class: MagicMock,
        exporter: CloudControlExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_proxy.get_paginator = MagicMock(
            return_value=_paginator_with(
                error=ClientError(
                    {"Error": {"Code": "InternalFailure", "Message": "boom"}},
                    "ListResources",
                )
            )
        )

        request = PaginatedCloudControlResourceRequest(
            region="us-east-1",
            account_id="123456789012",
            type_name="AWS::IAM::Role",
        )
        with pytest.raises(ClientError):
            async for _ in exporter.get_paginated_resources(request):
                pass

    @pytest.mark.asyncio
    async def test_inspector_preserves_arbitrary_properties(self) -> None:
        inspector = ResourceInspector(
            AsyncMock(),
            CloudControlExporter._actions_map(),
            lambda: CloudControlResource(Type="AWS::IAM::Role"),
            action_id_key="Identifier",
        )
        result = await inspector.inspect(
            CloudControlActionInput(
                items=[
                    CloudControlResourceIdentifier(
                        identifier="role-1",
                        properties={"RoleName": "admin", "Path": "/"},
                    )
                ],
                type_name="AWS::IAM::Role",
            ),
            include=[],
            extra_context={"AccountId": "123", "Region": "us-east-1"},
        )

        assert result[0]["Type"] == "AWS::IAM::Role"
        assert result[0]["Properties"]["Identifier"] == "role-1"
        assert result[0]["Properties"]["RoleName"] == "admin"
        assert result[0]["Properties"]["Path"] == "/"
        assert result[0]["__ExtraContext"]["AccountId"] == "123"
