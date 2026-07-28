from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.ses.email_identity.exporter import SesEmailIdentityExporter
from aws.core.exporters.ses.email_identity.models import (
    SingleEmailIdentityRequest,
    PaginatedEmailIdentityRequest,
)
from aws.core.exporters.ses.email_identity.regions import (
    SES_EMAIL_IDENTITY_SUPPORTED_REGIONS,
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

    def test_supported_regions(self, exporter: SesEmailIdentityExporter) -> None:
        assert exporter._supported_regions == SES_EMAIL_IDENTITY_SUPPORTED_REGIONS
        assert "us-east-1" in exporter._supported_regions
        assert "ap-southeast-4" not in exporter._supported_regions

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

        # Mock list_email_identities (no botocore paginator config exists for this operation)
        mock_client.list_email_identities.return_value = {
            "EmailIdentities": [
                {"EmailIdentity": "example.com", "IdentityType": "DOMAIN"},
                {
                    "EmailIdentity": "user@example.com",
                    "IdentityType": "EMAIL_ADDRESS",
                },
            ]
        }

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
    async def test_get_paginated_resources_follows_next_token(
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

        # list_email_identities has no botocore paginator config, so the exporter
        # must follow NextToken itself across multiple calls
        mock_client.list_email_identities.side_effect = [
            {
                "EmailIdentities": [
                    {"EmailIdentity": "example.com", "IdentityType": "DOMAIN"}
                ],
                "NextToken": "page-2",
            },
            {
                "EmailIdentities": [
                    {
                        "EmailIdentity": "user@example.com",
                        "IdentityType": "EMAIL_ADDRESS",
                    }
                ]
            },
        ]

        # Inspector
        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector
        mock_inspector.inspect.side_effect = lambda identities, *a, **kw: identities

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
        assert mock_client.list_email_identities.call_count == 2
        mock_client.list_email_identities.assert_any_call()
        mock_client.list_email_identities.assert_any_call(NextToken="page-2")

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

        # Mock list_email_identities returning no identities
        mock_client.list_email_identities.return_value = {"EmailIdentities": []}

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
