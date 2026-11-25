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
from aws.core.helpers.types import SupportedServices
from aws.core.helpers.utils import require_aws_resource
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
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await proxy.client.get_agent(agentId=options.agent_id)  # type: ignore[attr-defined]
            response.pop("ResponseMetadata", None)
            agent_data = require_aws_resource(
                [response["agent"]] if "agent" in response else [],
                error_code="ResourceNotFoundException",
                message=f"Agent not found: {options.agent_id}",
                operation_name="GetAgent",
            )
            action_result = await inspector.inspect(
                agent_data,
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
                        AgentIdentifier(agentId=agent["agentId"]) for agent in agents
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
