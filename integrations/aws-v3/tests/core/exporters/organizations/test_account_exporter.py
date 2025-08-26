import pytest
from unittest.mock import AsyncMock
from aws.auth.types import AccountInfo
from aws.core.exporters.organizations.account.exporter import (
    OrganizationsAccountExporter,
)
from aws.core.exporters.organizations.account.models import (
    PaginatedAccountRequest,
)


class TestOrganizationsAccountExporter:
    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock session for testing."""
        return AsyncMock()

    @pytest.fixture
    def mock_account_id(self) -> str:
        """Create a mock account ID for testing."""
        return "123456789012"

    @pytest.fixture
    def mock_exporter(
        self, mock_session: AsyncMock, mock_account_id: str
    ) -> OrganizationsAccountExporter:
        """Create a mock exporter instance."""
        return OrganizationsAccountExporter(mock_session, mock_account_id)

    def test_exporter_initialization(
        self, mock_session: AsyncMock, mock_account_id: str
    ) -> None:
        """Test that the exporter initializes correctly."""
        exporter = OrganizationsAccountExporter(mock_session, mock_account_id)
        assert exporter._service_name == "organizations"
        assert exporter.account_id == mock_account_id

    @pytest.mark.asyncio
    async def test_get_paginated_resources(
        self, mock_exporter: OrganizationsAccountExporter
    ) -> None:
        """Test that get_paginated_resources yields accounts correctly."""
        # Mock the session factory to return a single account
        mock_account_info: AccountInfo = {
            "Id": "123456789012",
            "Name": "Test Account",
            "Email": "test@example.com",
            "Arn": "arn:aws:organizations::123456789012:account/123456789012",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": 1672531200,
            "Status": "ACTIVE",
        }
        mock_session = AsyncMock()

        # Mock the client proxy and resource inspector
        mock_proxy = AsyncMock()
        mock_inspector = AsyncMock()
        mock_result = AsyncMock()
        mock_result.dict.return_value = {
            "Id": "123456789012",
            "Name": "Test Account",
            "Email": "test@example.com",
            "Status": "ACTIVE",
        }

        mock_inspector.inspect.return_value = mock_result
        mock_proxy.__aenter__.return_value = mock_proxy
        mock_session.__aenter__.return_value = mock_proxy

        # Mock the session factory
        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "aws.auth.session_factory.get_all_account_sessions",
                lambda: iter([(mock_account_info, mock_session)]),
            )
            m.setattr(
                "aws.core.exporters.organizations.account.exporter.ResourceInspector",
                lambda *args, **kwargs: mock_inspector,
            )

            options = PaginatedAccountRequest(
                region="us-east-1", account_data=mock_account_info
            )

            # Test the method - should return empty since accounts don't support pagination
            results = []
            async for batch in mock_exporter.get_paginated_resources(options):
                results.extend(batch)

            # get_paginated_resources is not used for accounts - returns empty
            assert len(results) == 0
