from dataclasses import dataclass
from typing import Any, Type

from aws.core.interfaces.action import Action, ActionMap, BaseActionInput
from aws.core.helpers.utils import execute_concurrent_aws_operations


@dataclass
class AgentIdentifier:
    agent_id: str
    agent_arn: str | None = None


@dataclass
class BedrockAgentActionInput(BaseActionInput[AgentIdentifier]):
    region: str
    account_id: str


class ListAgentsAction(Action[BedrockAgentActionInput]):
    """Pass-through action — returns the basic agent summary fields from list_agents."""

    async def _execute(self, resources: BedrockAgentActionInput) -> list[dict[str, Any]]:
        return [
            {
                "agentId": agent.agent_id,
            }
            for agent in resources.items
        ]


class GetAgentAction(Action[BedrockAgentActionInput]):
    """Fetches full agent details via get_agent for each agent."""

    async def _execute(self, resources: BedrockAgentActionInput) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_agent,
            get_resource_identifier=lambda agent: agent.agent_id,
            operation_name="Bedrock agent details",
        )

    async def _fetch_agent(self, agent: AgentIdentifier) -> dict[str, Any]:
        response = await self.client.get_agent(agentId=agent.agent_id)
        response.pop("ResponseMetadata", None)
        return response.get("agent", {})


class GetAgentTagsAction(Action[BedrockAgentActionInput]):
    """Fetches tags for each Bedrock Agent via list_tags_for_resource."""

    async def _execute(self, resources: BedrockAgentActionInput) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=resources.items,
            operation_func=self._fetch_agent_tags,
            get_resource_identifier=lambda agent: agent.agent_id,
            operation_name="Bedrock agent tags",
        )

    async def _fetch_agent_tags(self, agent: AgentIdentifier) -> dict[str, Any]:
        if not agent.agent_arn:
            return {"tags": None}
        response = await self.client.list_tags_for_resource(resourceArn=agent.agent_arn)
        response.pop("ResponseMetadata", None)
        return {"tags": response.get("tags")}


class BedrockAgentActionsMap(ActionMap[BedrockAgentActionInput]):
    """Groups all actions for Bedrock Agents."""

    defaults: list[Type[Action[BedrockAgentActionInput]]] = [
        ListAgentsAction,
        GetAgentAction,
    ]
    options: list[Type[Action[BedrockAgentActionInput]]] = [
        GetAgentTagsAction,
    ]
