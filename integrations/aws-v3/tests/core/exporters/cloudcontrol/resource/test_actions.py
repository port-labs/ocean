import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.cloudcontrol.resource.actions import (
    CloudControlActionInput,
    CloudControlActionsMap,
    CloudControlResourceIdentifier,
    GetResourceAction,
    ListResourcesAction,
)
from aws.core.interfaces.action import Action


def _action_input(
    *identifiers: str, properties: dict[str, Any] | None = None
) -> CloudControlActionInput:
    return CloudControlActionInput(
        items=[
            CloudControlResourceIdentifier(
                identifier=identifier,
                properties=properties or {},
            )
            for identifier in identifiers
        ],
        type_name="AWS::IAM::Role",
    )


class TestListResourcesAction:
    @pytest.fixture
    def action(self) -> ListResourcesAction:
        return ListResourcesAction(AsyncMock())

    def test_inheritance(self, action: ListResourcesAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_merges_identifier_over_properties(
        self, action: ListResourcesAction
    ) -> None:
        result = await action._execute(
            CloudControlActionInput(
                items=[
                    CloudControlResourceIdentifier(
                        identifier="role-1",
                        properties={"RoleName": "admin", "Identifier": "from-props"},
                    )
                ],
                type_name="AWS::IAM::Role",
            )
        )
        assert result == [{"RoleName": "admin", "Identifier": "role-1"}]

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListResourcesAction) -> None:
        result = await action._execute(
            CloudControlActionInput(items=[], type_name="AWS::IAM::Role")
        )
        assert result == []


class TestGetResourceAction:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        mock_client = AsyncMock()
        mock_client.get_resource = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetResourceAction:
        return GetResourceAction(mock_client)

    def test_inheritance(self, action: GetResourceAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetResourceAction) -> None:
        action.client.get_resource.return_value = {
            "ResourceDescription": {
                "Identifier": "role-1",
                "Properties": json.dumps(
                    {"RoleName": "admin", "Arn": "arn:aws:iam::123:role/admin"}
                ),
            }
        }

        result = await action._execute(_action_input("role-1"))

        assert result == [
            {
                "RoleName": "admin",
                "Arn": "arn:aws:iam::123:role/admin",
                "Identifier": "role-1",
            }
        ]
        action.client.get_resource.assert_awaited_once_with(
            TypeName="AWS::IAM::Role", Identifier="role-1"
        )

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: GetResourceAction) -> None:
        result = await action._execute(
            CloudControlActionInput(items=[], type_name="AWS::IAM::Role")
        )
        assert result == []
        action.client.get_resource.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: GetResourceAction
    ) -> None:
        action.client.get_resource.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "GetResource",
        )
        result = await action._execute(_action_input("missing-role"))
        assert result == [{}]

    @pytest.mark.asyncio
    async def test_execute_preserves_index_alignment_with_middle_failure(
        self, action: GetResourceAction
    ) -> None:
        async def mock_get_resource(TypeName: str, Identifier: str) -> dict[str, Any]:
            if Identifier == "role-2":
                raise ClientError(
                    {"Error": {"Code": "AccessDenied", "Message": "denied"}},
                    "GetResource",
                )
            return {
                "ResourceDescription": {
                    "Identifier": Identifier,
                    "Properties": json.dumps({"RoleName": Identifier}),
                }
            }

        action.client.get_resource.side_effect = mock_get_resource
        result = await action._execute(_action_input("role-1", "role-2", "role-3"))

        assert result == [
            {"RoleName": "role-1", "Identifier": "role-1"},
            {},
            {"RoleName": "role-3", "Identifier": "role-3"},
        ]

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: GetResourceAction
    ) -> None:
        action.client.get_resource.side_effect = ClientError(
            {"Error": {"Code": "InvalidRequest", "Message": "bad"}},
            "GetResource",
        )
        with pytest.raises(ClientError):
            await action._execute(_action_input("role-1"))


class TestCloudControlActionsMap:
    def test_defaults_and_options(self) -> None:
        actions_map = CloudControlActionsMap()
        assert actions_map.defaults == [ListResourcesAction]
        assert actions_map.options == [GetResourceAction]

    def test_merge_includes_get_resource_when_requested(self) -> None:
        merged = CloudControlActionsMap().merge(["GetResourceAction"])
        assert merged == [ListResourcesAction, GetResourceAction]
