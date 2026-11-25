from dataclasses import dataclass
from typing import Any, Type

from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from aws.core.helpers.utils import execute_concurrent_aws_operations


@dataclass
class AgentIdentifier:
    agentId: str


@dataclass
class BedrockAgentActionInput(BaseActionInput[AgentIdentifier]):
    region: str
    account_id: str


class ListAgentsAction(Action[BedrockAgentActionInput]):
    async def _execute(self, resources: BedrockAgentActionInput) -> list[dict[str, Any]]:
        return [{"agentId": agent.agentId} for agent in resources.items]


class GetAgentAction(Action[BedrockAgentActionInput]):
    async def _execute(self, resources: BedrockAgentActionInput) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_agent,
            get_resource_identifier=lambda agent: agent.agentId,
            operation_name="agent details",
        )

    async def _fetch_agent(self, agent: AgentIdentifier) -> dict[str, Any]:
        response = await self.client.get_agent(agentId=agent.agentId)
        response.pop("ResponseMetadata", None)
        agent_data = response.get("agent", {})
        return agent_data


class BedrockAgentActionsMap(ActionMap[BedrockAgentActionInput]):
    defaults: list[Type[Action[BedrockAgentActionInput]]] = [
        ListAgentsAction,
        GetAgentAction,
    ]
    options: list[Type[Action[BedrockAgentActionInput]]] = []
