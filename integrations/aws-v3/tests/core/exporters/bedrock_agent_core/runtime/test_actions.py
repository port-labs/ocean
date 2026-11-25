from typing import Any
from unittest.mock import AsyncMock

import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.bedrock_agent_core.runtime.actions import (
    BedrockAgentCoreRuntimeActionsMap,
    GetAgentRuntimeAction,
    ListAgentRuntimesAction,
)
from aws.core.interfaces.action import Action


RUNTIME_ID = "my-runtime-Ab1Cd2Ef3G"
RUNTIME_ARN = f"arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/{RUNTIME_ID}"

SAMPLE_LIST_ITEM: dict[str, Any] = {
    "agentRuntimeId": RUNTIME_ID,
    "agentRuntimeArn": RUNTIME_ARN,
    "agentRuntimeName": "my-runtime",
    "agentRuntimeVersion": "1",
    "description": "Test runtime",
    "status": "READY",
    "lastUpdatedAt": "2025-06-01T12:00:00Z",
}

SAMPLE_GET_RESPONSE: dict[str, Any] = {
    **SAMPLE_LIST_ITEM,
    "createdAt": "2025-05-15T09:30:00Z",
    "roleArn": "arn:aws:iam::123456789012:role/MyRole",
    "networkConfiguration": {"networkMode": "PUBLIC"},
    "platformVersion": "1.0",
    "lifecycleConfiguration": {"idleRuntimeSessionTimeout": 3600},
    "metadataConfiguration": None,
    "agentRuntimeArtifact": {
        "containerConfiguration": {
            "containerUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-agent:latest"
        }
    },
    "ResponseMetadata": {
        "RequestId": "abc123",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {},
    },
}


class TestListAgentRuntimesAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListAgentRuntimesAction:
        return ListAgentRuntimesAction(mock_client)

    def test_inheritance(self, action: ListAgentRuntimesAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_returns_list_of_dicts(
        self, action: ListAgentRuntimesAction
    ) -> None:
        result = await action._execute([SAMPLE_LIST_ITEM])
        assert len(result) == 1
        assert result[0]["agentRuntimeId"] == RUNTIME_ID
        assert result[0]["agentRuntimeName"] == "my-runtime"

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListAgentRuntimesAction) -> None:
        result = await action._execute([])
        assert result == []


class TestGetAgentRuntimeAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.get_agent_runtime = AsyncMock(return_value=SAMPLE_GET_RESPONSE.copy())
        return client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetAgentRuntimeAction:
        return GetAgentRuntimeAction(mock_client)

    def test_inheritance(self, action: GetAgentRuntimeAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetAgentRuntimeAction) -> None:
        result = await action._execute([SAMPLE_LIST_ITEM])

        assert len(result) == 1
        assert result[0]["agentRuntimeId"] == RUNTIME_ID
        assert result[0]["agentRuntimeArn"] == RUNTIME_ARN
        assert result[0]["status"] == "READY"
        assert "ResponseMetadata" not in result[0]

        action.client.get_agent_runtime.assert_awaited_once_with(
            agentRuntimeId=RUNTIME_ID
        )

    @pytest.mark.asyncio
    async def test_execute_strips_response_metadata(
        self, action: GetAgentRuntimeAction
    ) -> None:
        result = await action._execute([SAMPLE_LIST_ITEM])
        assert "ResponseMetadata" not in result[0]

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: GetAgentRuntimeAction) -> None:
        result = await action._execute([])
        assert result == []
        action.client.get_agent_runtime.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: GetAgentRuntimeAction
    ) -> None:
        action.client.get_agent_runtime.side_effect = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException"}},
            operation_name="GetAgentRuntime",
        )
        result = await action._execute([SAMPLE_LIST_ITEM])
        assert result == [{}]

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: GetAgentRuntimeAction
    ) -> None:
        action.client.get_agent_runtime.side_effect = ClientError(
            error_response={"Error": {"Code": "InternalServerException"}},
            operation_name="GetAgentRuntime",
        )
        with pytest.raises(ClientError):
            await action._execute([SAMPLE_LIST_ITEM])

    @pytest.mark.asyncio
    async def test_execute_preserves_index_alignment_with_middle_failure(
        self, action: GetAgentRuntimeAction
    ) -> None:
        runtimes = [
            {**SAMPLE_LIST_ITEM, "agentRuntimeId": "runtime-1"},
            {**SAMPLE_LIST_ITEM, "agentRuntimeId": "runtime-2"},
            {**SAMPLE_LIST_ITEM, "agentRuntimeId": "runtime-3"},
        ]

        def mock_get(agentRuntimeId: str, **kwargs: Any) -> dict[str, Any]:
            if agentRuntimeId == "runtime-2":
                raise ClientError(
                    error_response={"Error": {"Code": "AccessDeniedException"}},
                    operation_name="GetAgentRuntime",
                )
            response = SAMPLE_GET_RESPONSE.copy()
            response["agentRuntimeId"] = agentRuntimeId
            return response

        action.client.get_agent_runtime.side_effect = mock_get

        result = await action._execute(runtimes)

        assert len(result) == 3
        assert result[0]["agentRuntimeId"] == "runtime-1"
        assert result[1] == {}
        assert result[2]["agentRuntimeId"] == "runtime-3"


class TestBedrockAgentCoreRuntimeActionsMap:

    def test_defaults_contain_expected_actions(self) -> None:
        actions_map = BedrockAgentCoreRuntimeActionsMap()
        assert ListAgentRuntimesAction in actions_map.defaults
        assert GetAgentRuntimeAction in actions_map.defaults

    def test_no_options(self) -> None:
        actions_map = BedrockAgentCoreRuntimeActionsMap()
        assert actions_map.options == []
