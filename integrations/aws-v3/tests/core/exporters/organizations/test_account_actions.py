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

        assert result == [{"Parents": [{"Id": "r-root"}, {"Id": "ou-abcd-1234"}]}]
        action.client.get_paginator.assert_called_once_with("list_parents")


class TestListTagsForResourceAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        mock_client = AsyncMock()

        class MockPaginator:
            def paginate(self, **kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
                async def _gen() -> AsyncGenerator[Dict[str, Any], None]:
                    yield {"Tags": [{"Key": "Env", "Value": "prod"}]}

                return _gen()

        mock_client.get_paginator = MagicMock(return_value=MockPaginator())
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
        result = await action.execute([{"Id": "111111111111"}])

        assert result == [{"Tags": [{"Key": "Env", "Value": "prod"}]}]
        action.client.get_paginator.assert_called_once_with("list_tags_for_resource")

    @pytest.mark.asyncio
    @patch("aws.core.exporters.organizations.account.actions.logger")
    async def test_execute_handles_error(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        # Mock accounts to test with
        accounts = [
            {"Id": "111111111111"},  # Will raise access denied
            {"Id": "222222222222"},  # Will raise resource not found
            {"Id": "333333333333"},  # Will raise other exception
            {"Id": "444444444444"},  # Will succeed
        ]

        # Mock paginator behavior for the successful case
        class MockPaginator:
            def paginate(self, **kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
                async def _gen() -> AsyncGenerator[Dict[str, Any], None]:
                    if kwargs["ResourceId"] == "444444444444":
                        yield {"Tags": [{"Key": "Env", "Value": "prod"}]}
                    elif kwargs["ResourceId"] == "111111111111":
                        raise Exception("AccessDeniedException")
                    elif kwargs["ResourceId"] == "222222222222":
                        raise Exception("ResourceNotFoundException")
                    else:
                        raise Exception("UnexpectedError")

                return _gen()

        action.client.get_paginator = MagicMock(return_value=MockPaginator())

        # Mock error type checking functions
        with (
            patch(
                "aws.core.exporters.organizations.account.actions.is_access_denied_exception",
                side_effect=lambda e: "AccessDeniedException" in str(e),
            ),
            patch(
                "aws.core.exporters.organizations.account.actions.is_resource_not_found_exception",
                side_effect=lambda e: "ResourceNotFoundException" in str(e),
            ),
        ):
            # Execute and verify results
            with pytest.raises(Exception) as exc_info:
                await action.execute(accounts)
                assert str(exc_info.value) == "UnexpectedError"

            # Verify warning logs for access denied and resource not found
            mock_logger.warning.assert_any_call(
                "Administrator or management account has been denied access to list tags for account 111111111111, AccessDeniedException, skipping ..."
            )
            mock_logger.warning.assert_any_call(
                "Failed to list tags for account 222222222222: ResourceNotFoundException"
            )


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
