from datetime import datetime
from typing import Any, NotRequired, Type, TypedDict

from aws.core.helpers.utils import execute_concurrent_aws_operations
from aws.core.interfaces.action import Action, ActionMap


class AgentRuntimeRecord(TypedDict):
    """A runtime as the actions receive it.

    Resync feeds ``list_agent_runtimes`` items (all fields); a single-resource
    fetch feeds only the ID and the ARN.
    """

    agentRuntimeId: str
    agentRuntimeArn: str
    agentRuntimeName: NotRequired[str]
    agentRuntimeVersion: NotRequired[str]
    description: NotRequired[str]
    status: NotRequired[str]
    lastUpdatedAt: NotRequired[datetime]


class ListAgentRuntimesAction(Action[list[AgentRuntimeRecord]]):
    """Pass-through action for list_agent_runtimes items (ID, ARN, name, status)."""

    async def _execute(
        self, runtimes: list[AgentRuntimeRecord]
    ) -> list[dict[str, Any]]:
        return [dict(runtime) for runtime in runtimes]


class GetAgentRuntimeAction(Action[list[AgentRuntimeRecord]]):
    """Fetches full details (role, artifact, network, protocol, auth) per runtime."""

    async def _execute(
        self, runtimes: list[AgentRuntimeRecord]
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=runtimes,
            operation_func=self._fetch_runtime_details,
            get_resource_identifier=lambda runtime: runtime["agentRuntimeId"],
            operation_name="AgentCore runtime details",
        )

    async def _fetch_runtime_details(
        self, runtime: AgentRuntimeRecord
    ) -> dict[str, Any]:
        response = await self.client.get_agent_runtime(
            agentRuntimeId=runtime["agentRuntimeId"]
        )
        response.pop("ResponseMetadata", None)
        return response


class ListAgentRuntimeTagsAction(Action[list[AgentRuntimeRecord]]):
    """Fetches tags, kept in the map shape AWS returns."""

    async def _execute(
        self, runtimes: list[AgentRuntimeRecord]
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=runtimes,
            operation_func=self._fetch_tags,
            get_resource_identifier=lambda runtime: runtime["agentRuntimeId"],
            operation_name="AgentCore runtime tags",
        )

    async def _fetch_tags(self, runtime: AgentRuntimeRecord) -> dict[str, Any]:
        response = await self.client.list_tags_for_resource(
            resourceArn=runtime["agentRuntimeArn"]
        )
        return {"tags": response.get("tags", {})}


class BedrockAgentCoreRuntimeActionsMap(ActionMap[list[AgentRuntimeRecord]]):
    """Groups all actions for BedrockAgentCore Runtimes."""

    defaults: list[Type[Action[list[AgentRuntimeRecord]]]] = [
        ListAgentRuntimesAction,
        GetAgentRuntimeAction,
    ]
    options: list[Type[Action[list[AgentRuntimeRecord]]]] = [
        ListAgentRuntimeTagsAction,
    ]
