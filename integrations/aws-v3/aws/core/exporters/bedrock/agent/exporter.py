from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.bedrock.agent.actions import (
    BedrockAgentActionsMap,
    BedrockAgentActionInput,
    AgentIdentifier,
)
from aws.core.exporters.bedrock.agent.models import (
    Agent,
    SingleAgentRequest,
    PaginatedAgentRequest,
)
from aws.core.exporters.bedrock.agent.regions import BEDROCK_AGENT_SUPPORTED_REGIONS
from aws.core.exporters.bedrock.agent.utils import build_agent_arn
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from loguru import logger


class BedrockAgentExporter(IResourceExporter[BedrockAgentActionInput]):
    _service_name: SupportedServices = "bedrock-agent"
    _model_cls: Type[Agent] = Agent
    _actions_map: Type[BedrockAgentActionsMap] = BedrockAgentActionsMap
    _supported_regions: frozenset[str] = BEDROCK_AGENT_SUPPORTED_REGIONS

    async def get_resource(self, options: SingleAgentRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single Bedrock Agent."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            # GetAgentAction swallows ResourceNotFound as recoverable, so the
            # inspector would build a stub from ListAgentsAction for a deleted agent.
            # Confirm it exists so a missing agent raises and the live-event handler
            # can treat the update as a delete instead.
            await proxy.client.get_agent(agentId=options.agent_id)  # type: ignore[attr-defined]

            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            action_result = await inspector.inspect(
                BedrockAgentActionInput(
                    items=[
                        AgentIdentifier(
                            agentId=options.agent_id,
                            agentArn=build_agent_arn(
                                options.region, options.account_id, options.agent_id
                            ),
                        )
                    ],
                    region=options.region,
                    account_id=options.account_id,
                ),
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return action_result[0] if action_result else {}

    async def get_paginated_resources(
        self, options: PaginatedAgentRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all Bedrock Agents in the region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_agents", "agentSummaries")

            async for agents in paginator.paginate():
                if agents:
                    agent_items = [
                        AgentIdentifier(
                            agentId=agent["agentId"],
                            agentArn=build_agent_arn(
                                options.region, options.account_id, agent["agentId"]
                            ),
                        )
                        for agent in agents
                    ]
                    result = await inspector.inspect(
                        BedrockAgentActionInput(
                            items=agent_items,
                            region=options.region,
                            account_id=options.account_id,
                        ),
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield result
                else:
                    logger.debug(
                        f"No agents returned from paginator for region {options.region}, yielding empty batch"
                    )
                    yield []
