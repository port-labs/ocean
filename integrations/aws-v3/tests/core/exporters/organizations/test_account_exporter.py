from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.organizations.account.exporter import (
    OrganizationsAccountExporter,
)
from aws.core.exporters.organizations.account.models import (
    SingleAccountRequest,
    PaginatedAccountRequest,
    Account,
    AccountProperties,
)


class TestOrganizationsAccountExporter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def exporter(self, mock_session: AsyncMock) -> OrganizationsAccountExporter:
        return OrganizationsAccountExporter(mock_session)

    def test_service_name(self, exporter: OrganizationsAccountExporter) -> None:
        assert exporter._service_name == "organizations"

    def test_initialization(self, mock_session: AsyncMock) -> None:
        exporter = OrganizationsAccountExporter(mock_session)
        assert exporter.session == mock_session
        assert exporter._client is None

    @pytest.mark.asyncio
    @patch("aws.core.exporters.organizations.account.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.organizations.account.exporter.ResourceInspector")
    async def test_get_resource_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: OrganizationsAccountExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        expected = Account(
            Properties=AccountProperties(
                Id="111111111111",
                Name="prod",
                Email="a@b.com",
            )
        )
        mock_inspector.inspect.return_value = [expected.dict(exclude_none=True)]

        options = SingleAccountRequest(
            region="us-east-1",
            account_id="111111111111",
            include=["ListParentsAction"],
        )

        result = await exporter.get_resource(options)

        assert result == expected.dict(exclude_none=True)
        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "organizations"
        )
        mock_inspector_class.assert_called_once()
        mock_inspector.inspect.assert_called_once_with(
            [{"Id": "111111111111"}], ["ListParentsAction"]
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.organizations.account.exporter.AioBaseClientProxy")
    @patch("aws.core.exporters.organizations.account.exporter.ResourceInspector")
    async def test_get_paginated_resources_success(
        self,
        mock_inspector_class: MagicMock,
        mock_proxy_class: MagicMock,
        exporter: OrganizationsAccountExporter,
    ) -> None:
        mock_proxy = AsyncMock()
        mock_client = AsyncMock()
        mock_proxy.client = mock_client
        mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

        async def mock_paginate() -> AsyncGenerator[list[dict[str, str]], None]:
            yield [{"Id": "111111111111"}, {"Id": "222222222222"}]
            yield [{"Id": "333333333333"}]

        class MockPaginator:
            def paginate(self) -> AsyncGenerator[list[dict[str, str]], None]:
                return mock_paginate()

        paginator_instance = MockPaginator()
        mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

        mock_inspector = AsyncMock()
        mock_inspector_class.return_value = mock_inspector

        acc1 = Account(Properties=AccountProperties(Id="111111111111"))
        acc2 = Account(Properties=AccountProperties(Id="222222222222"))
        acc3 = Account(Properties=AccountProperties(Id="333333333333"))

        mock_inspector.inspect.side_effect = [
            [acc1.dict(exclude_none=True), acc2.dict(exclude_none=True)],
            [acc3.dict(exclude_none=True)],
        ]

        options = PaginatedAccountRequest(
            region="us-east-1", account_id="999999999999", include=["ListParentsAction"]
        )

        results = []
        async for page in exporter.get_paginated_resources(options):
            results.extend(page)

        assert len(results) == 3
        assert results[0] == acc1.dict(exclude_none=True)
        assert results[1] == acc2.dict(exclude_none=True)
        assert results[2] == acc3.dict(exclude_none=True)

        mock_proxy_class.assert_called_once_with(
            exporter.session, "us-east-1", "organizations"
        )
        mock_proxy.get_paginator.assert_called_once_with("list_accounts", "Accounts")
        assert mock_inspector.inspect.call_count == 2
        mock_inspector.inspect.assert_any_call(
            [{"Id": "111111111111"}, {"Id": "222222222222"}], ["ListParentsAction"]
        )
        mock_inspector.inspect.assert_any_call(
            [{"Id": "333333333333"}], ["ListParentsAction"]
        )
