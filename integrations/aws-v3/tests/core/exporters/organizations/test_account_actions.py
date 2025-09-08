from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from aws.core.exporters.organizations.account.actions import (
    ListAccountsAction,
    ListParentsAction,
    ListTagsForResourceAction,
    OrganizationsAccountActionsMap,
)
from aws.core.interfaces.action import Action


class TestListAccountsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListAccountsAction:
        return ListAccountsAction(mock_client)

    def test_inheritance(self, action: ListAccountsAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_passthrough(self, action: ListAccountsAction) -> None:
        identifiers = [{"Id": "111111111111"}, {"Id": "222222222222"}]
        result = await action.execute(identifiers)
        assert result == identifiers


class TestListParentsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        mock_client = AsyncMock()

        class MockPaginator:
            def paginate(self, **kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
                async def _gen() -> AsyncGenerator[Dict[str, Any], None]:
                    # First page: one parent
                    yield {"Parents": [{"Id": "r-root"}]}
                    # Second page: another parent
                    yield {"Parents": [{"Id": "ou-abcd-1234"}]}

                return _gen()

        mock_client.get_paginator = MagicMock(return_value=MockPaginator())
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListParentsAction:
        return ListParentsAction(mock_client)

    def test_inheritance(self, action: ListParentsAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.organizations.account.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: ListParentsAction
    ) -> None:
        identifiers = [{"Id": "111111111111"}]
        result = await action.execute(identifiers)

        assert result == [{"ParentIds": ["r-root", "ou-abcd-1234"]}]
        action.client.get_paginator.assert_called_once_with("list_parents")


class TestListTagsForResourceAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        mock_client = AsyncMock()
        mock_client.list_tags_for_resource = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListTagsForResourceAction:
        return ListTagsForResourceAction(mock_client)

    def test_inheritance(self, action: ListTagsForResourceAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    @patch("aws.core.exporters.organizations.account.actions.logger")
    async def test_execute_success(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        action.client.list_tags_for_resource.return_value = {
            "Tags": [{"Key": "Env", "Value": "prod"}]
        }

        result = await action.execute([{"Id": "111111111111"}])

        assert result == [{"Tags": [{"Key": "Env", "Value": "prod"}]}]
        action.client.list_tags_for_resource.assert_called_once_with(
            ResourceId="111111111111"
        )

    @pytest.mark.asyncio
    @patch("aws.core.exporters.organizations.account.actions.logger")
    async def test_execute_handles_error(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        action.client.list_tags_for_resource.side_effect = Exception("throttle")

        result = await action.execute([{"Id": "111111111111"}])

        assert result == [{"Tags": []}]
        mock_logger.warning.assert_called()


class TestOrganizationsAccountActionsMap:
    def test_merge_defaults_only(self) -> None:
        actions = OrganizationsAccountActionsMap().merge([])
        assert ListAccountsAction in actions
        assert ListParentsAction not in actions
        assert ListTagsForResourceAction not in actions

    def test_merge_with_options(self) -> None:
        include = ["ListParentsAction", "ListTagsForResourceAction"]
        actions = OrganizationsAccountActionsMap().merge(include)
        names = [a.__name__ for a in actions]
        assert "ListAccountsAction" in names
        assert "ListParentsAction" in names
        assert "ListTagsForResourceAction" in names
