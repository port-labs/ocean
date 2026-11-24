from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.bedrock.agent.actions import (
    BedrockAgentActionsMap,
    BedrockAgentActionInput,
    AgentIdentifier,
)
from aws.core.exporters.bedrock.agent.models import (
    BedrockAgent,
    SingleBedrockAgentRequest,
    PaginatedBedrockAgentRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from loguru import logger


class BedrockAgentExporter(IResourceExporter[BedrockAgentActionInput]):
    _service_name: SupportedServices = "bedrock-agent"
    _model_cls: Type[BedrockAgent] = BedrockAgent
    _actions_map: Type[BedrockAgentActionsMap] = BedrockAgentActionsMap

    async def get_resource(self, options: SingleBedrockAgentRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single Bedrock Agent."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            # Confirm the agent exists — raises if not found so the live-event
            # handler can treat the update as a delete.
            response = await proxy.client.get_agent(  # type: ignore[attr-defined]
                agentId=options.agent_id
            )
            agent_data = response.get("agent", {})
            agent_arn = agent_data.get("agentArn")

            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            result = await inspector.inspect(
                BedrockAgentActionInput(
                    items=[
                        AgentIdentifier(
                            agent_id=options.agent_id,
                            agent_arn=agent_arn,
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
            return result[0] if result else {}

    async def get_paginated_resources(
        self, options: PaginatedBedrockAgentRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all Bedrock Agents in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_agents", "agentSummaries")

            async for agent_summaries in paginator.paginate():
                if agent_summaries:
                    agent_items = [
                        AgentIdentifier(
                            agent_id=summary["agentId"],
                            agent_arn=None,  # ARN is not in list_agents; GetAgentAction fetches it
                        )
                        for summary in agent_summaries
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
                        f"No Bedrock Agents returned from paginator for region {options.region}, yielding empty batch"
                    )
                    yield []
