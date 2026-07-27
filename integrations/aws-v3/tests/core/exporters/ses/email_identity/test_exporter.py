from typing import AsyncGenerator, List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ses.email_identity.exporter import SesEmailIdentityExporter
from aws.core.exporters.ses.email_identity.models import (
    SingleEmailIdentityRequest,
    PaginatedEmailIdentityRequest,
)


class TestSesEmailIdentityExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> SesEmailIdentityExporter:
        return SesEmailIdentityExporter(mock_session)

    def test_service_name(self, exporter: SesEmailIdentityExporter) -> None:
        assert exporter._service_name == "sesv2"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = SesEmailIdentityExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.ses.email_identity.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.ses.email_identity.exporter.ResourceInspector"
    )
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesEmailIdentityExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock get_email_identity response
        mock_client.get_email_identity.return_value = {
            "IdentityType": "DOMAIN",
            "VerifiedForSendingStatus": True,
            "DkimEnabled": True,
        }

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_identity_data = {
            "EmailIdentity": "example.com",
            "IdentityType": "DOMAIN",
            "VerifiedForSendingStatus": True,
            "DkimEnabled": True,
        }
        mock_inspector.inspect.return_value = [mock_identity_data]

        # Create request
        request = SingleEmailIdentityRequest(
            email_identity="example.com",
            region="us-east-1",
            include=["GetEmailIdentityAction"],
            account_id="123456789012",
        )

        # Execute
        result = await exporter.get_resource(request)

        # Verify
        assert isinstance(result, dict)
        assert result["EmailIdentity"] == "example.com"
        assert result["IdentityType"] == "DOMAIN"

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.ses.email_identity.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.ses.email_identity.exporter.ResourceInspector"
    )
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesEmailIdentityExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock paginator
        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                {"EmailIdentity": "example.com", "IdentityType": "DOMAIN"},
                {
                    "EmailIdentity": "user@example.com",
                    "IdentityType": "EMAIL_ADDRESS",
                },
            ]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        mock_identity_data = [
            {
                "EmailIdentity": "example.com",
                "IdentityType": "DOMAIN",
                "VerifiedForSendingStatus": True,
            },
            {
                "EmailIdentity": "user@example.com",
                "IdentityType": "EMAIL_ADDRESS",
                "VerifiedForSendingStatus": True,
            },
        ]
        mock_inspector.inspect.return_value = mock_identity_data

        # Create request
        request = PaginatedEmailIdentityRequest(
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
        assert results[0]["EmailIdentity"] == "example.com"
        assert results[1]["EmailIdentity"] == "user@example.com"

    @pytest.mark.asyncio
    @patch(
        "aws.core.exporters.ses.email_identity.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.ses.email_identity.exporter.ResourceInspector"
    )
    async def test_get_paginated_resources_empty(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesEmailIdentityExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        # Mock paginator returning empty list
        async def mock_paginate() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield []

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
                return mock_paginate()

        mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.return_value = []

        # Create request
        request = PaginatedEmailIdentityRequest(
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
    @patch(
        "aws.core.exporters.ses.email_identity.exporter.AioBaseClientProxy"
    )
    @patch(
        "aws.core.exporters.ses.email_identity.exporter.ResourceInspector"
    )
    async def test_get_resource_inspector_exception(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: SesEmailIdentityExporter,
    ) -> None:
        # Setup proxy/client
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_client.get_email_identity.return_value = {
            "IdentityType": "DOMAIN",
            "VerifiedForSendingStatus": True,
        }

        # Inspector raises exception
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = Exception("Inspector error")

        # Create request
        request = SingleEmailIdentityRequest(
            email_identity="example.com",
            region="us-east-1",
            include=[],
            account_id="123456789012",
        )

        # Execute and verify exception is raised
        with pytest.raises(Exception, match="Inspector error"):
            await exporter.get_resource(request)
