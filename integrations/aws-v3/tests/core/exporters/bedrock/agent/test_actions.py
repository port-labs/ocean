from typing import Any
from unittest.mock import AsyncMock
import pytest
from botocore.exceptions import ClientError

from aws.core.exporters.bedrock.agent.actions import (
    BedrockAgentActionsMap,
    BedrockAgentActionInput,
    AgentIdentifier,
    GetAgentAction,
    ListAgentsAction,
    ListAgentTagsAction,
)
from aws.core.interfaces.action import Action


def _agent_arn(agent_id: str) -> str:
    return f"arn:aws:bedrock:us-east-1:123456789012:agent/{agent_id}"


def _make_input(
    agent_ids: list[str],
    region: str = "us-east-1",
    account_id: str = "123456789012",
) -> BedrockAgentActionInput:
    return BedrockAgentActionInput(
        items=[
            AgentIdentifier(agentId=agent_id, agentArn=_agent_arn(agent_id))
            for agent_id in agent_ids
        ],
        region=region,
        account_id=account_id,
    )


class TestListAgentsAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListAgentsAction:
        return ListAgentsAction(mock_client)

    def test_inheritance(self, action: ListAgentsAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: ListAgentsAction) -> None:
        action_input = _make_input(["ABCDEF1234", "GHIJKL5678"])

        result = await action._execute(action_input)

        assert len(result) == 2
        assert result[0] == {
            "agentId": "ABCDEF1234",
            "agentArn": _agent_arn("ABCDEF1234"),
        }
        assert result[1] == {
            "agentId": "GHIJKL5678",
            "agentArn": _agent_arn("GHIJKL5678"),
        }

    @pytest.mark.asyncio
    async def test_execute_empty_list(self, action: ListAgentsAction) -> None:
        action_input = _make_input([])
        result = await action._execute(action_input)
        assert result == []


class TestGetAgentAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        mock_client = AsyncMock()
        mock_client.get_agent = AsyncMock()
        return mock_client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetAgentAction:
        return GetAgentAction(mock_client)

    def test_inheritance(self, action: GetAgentAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(self, action: GetAgentAction) -> None:
        action.client.get_agent.return_value = {
            "agent": {
                "agentId": "ABCDEF1234",
                "agentName": "my-agent",
                "agentArn": "arn:aws:bedrock:us-east-1:123456789012:agent/ABCDEF1234",
                "agentStatus": "PREPARED",
                "agentVersion": "DRAFT",
                "foundationModel": "anthropic.claude-3-sonnet-20240229-v1:0",
                "idleSessionTTLInSeconds": 600,
                "createdAt": "2024-01-15T10:30:00.000Z",
                "updatedAt": "2024-01-20T14:45:00.000Z",
            }
        }

        action_input = _make_input(["ABCDEF1234"])
        result = await action._execute(action_input)

        assert len(result) == 1
        assert result[0]["agentId"] == "ABCDEF1234"
        assert result[0]["agentName"] == "my-agent"
        assert result[0]["agentStatus"] == "PREPARED"
        assert result[0]["foundationModel"] == "anthropic.claude-3-sonnet-20240229-v1:0"

        action.client.get_agent.assert_called_once_with(agentId="ABCDEF1234")

    @pytest.mark.asyncio
    async def test_execute_with_recoverable_exception(
        self, action: GetAgentAction
    ) -> None:
        error = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException"}},
            operation_name="GetAgent",
        )
        action.client.get_agent.side_effect = error

        action_input = _make_input(["ABCDEF1234"])
        result = await action._execute(action_input)

        assert result == [{}]

    @pytest.mark.asyncio
    async def test_execute_preserves_index_alignment_with_middle_failure(
        self, action: GetAgentAction
    ) -> None:
        def mock_get_agent(agentId: str, **kwargs: Any) -> dict[str, Any]:
            if agentId == "GHIJKL5678":
                raise ClientError(
                    error_response={"Error": {"Code": "AccessDenied"}},
                    operation_name="GetAgent",
                )
            return {"agent": {"agentId": agentId, "agentName": f"agent-{agentId}"}}

        action.client.get_agent.side_effect = mock_get_agent

        action_input = _make_input(["ABCDEF1234", "GHIJKL5678", "MNOPQR9012"])

        result = await action._execute(action_input)

        assert len(result) == 3
        assert result[0]["agentId"] == "ABCDEF1234"
        assert result[1] == {}
        assert result[2]["agentId"] == "MNOPQR9012"

    @pytest.mark.asyncio
    async def test_execute_with_non_recoverable_exception(
        self, action: GetAgentAction
    ) -> None:
        error = ClientError(
            error_response={"Error": {"Code": "InvalidParameterException"}},
            operation_name="GetAgent",
        )
        action.client.get_agent.side_effect = error

        action_input = _make_input(["ABCDEF1234"])

        with pytest.raises(ClientError):
            await action._execute(action_input)


class TestListAgentTagsAction:

    @pytest.fixture
    def action(self) -> ListAgentTagsAction:
        return ListAgentTagsAction(AsyncMock())

    @pytest.mark.asyncio
    async def test_execute_keeps_tags_as_map(self, action: ListAgentTagsAction) -> None:
        action.client.list_tags_for_resource.return_value = {
            "tags": {"Environment": "production"}
        }

        result = await action._execute(_make_input(["ABCDEF1234"]))

        assert result == [{"tags": {"Environment": "production"}}]
        action.client.list_tags_for_resource.assert_called_once_with(
            resourceArn=_agent_arn("ABCDEF1234")
        )

    @pytest.mark.asyncio
    async def test_execute_access_denied_returns_empty(
        self, action: ListAgentTagsAction
    ) -> None:
        action.client.list_tags_for_resource.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDeniedException"}},
            operation_name="ListTagsForResource",
        )

        result = await action._execute(_make_input(["ABCDEF1234"]))

        assert result == [{}]


class TestBedrockAgentActionsMap:

    def test_defaults(self) -> None:
        actions_map = BedrockAgentActionsMap()
        assert ListAgentsAction in actions_map.defaults
        assert GetAgentAction in actions_map.defaults

    def test_options(self) -> None:
        actions_map = BedrockAgentActionsMap()
        assert actions_map.options == [ListAgentTagsAction]
