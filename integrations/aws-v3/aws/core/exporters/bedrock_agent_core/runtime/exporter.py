from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.bedrock_agent_core.runtime.actions import (
    AgentRuntimeRecord,
    BedrockAgentCoreRuntimeActionsMap,
)
from aws.core.exporters.bedrock_agent_core.runtime.models import (
    BedrockAgentCoreRuntime,
    PaginatedBedrockAgentCoreRuntimeRequest,
    SingleBedrockAgentCoreRuntimeRequest,
)
from aws.core.exporters.bedrock_agent_core.runtime.regions import (
    BEDROCK_AGENT_CORE_RUNTIME_SUPPORTED_REGIONS,
)
from aws.core.exporters.bedrock_agent_core.runtime.utils import (
    build_agent_runtime_arn,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class BedrockAgentCoreRuntimeExporter(IResourceExporter[list[AgentRuntimeRecord]]):
    _service_name: SupportedServices = "bedrock-agentcore-control"
    _model_cls: Type[BedrockAgentCoreRuntime] = BedrockAgentCoreRuntime
    _actions_map: Type[BedrockAgentCoreRuntimeActionsMap] = (
        BedrockAgentCoreRuntimeActionsMap
    )
    _supported_regions: frozenset[str] = BEDROCK_AGENT_CORE_RUNTIME_SUPPORTED_REGIONS

    async def get_resource(
        self, options: SingleBedrockAgentCoreRuntimeRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single BedrockAgentCore Runtime."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            # Live-event single fetch only has the runtime ID from CloudTrail.
            # GetAgentRuntimeAction swallows ResourceNotFound as recoverable, so the
            # inspector would build a stub from the seeded identifiers for a deleted
            # runtime. Confirm it exists so a missing runtime raises and the
            # live-event handler can treat the update as a delete instead.
            await proxy.client.get_agent_runtime(  # type: ignore[attr-defined]
                agentRuntimeId=options.agent_runtime_id
            )

            # Seed only the identifiers; the tags action needs the ARN.
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [
                    AgentRuntimeRecord(
                        agentRuntimeId=options.agent_runtime_id,
                        agentRuntimeArn=build_agent_runtime_arn(
                            options.region,
                            options.account_id,
                            options.agent_runtime_id,
                        ),
                    )
                ],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedBedrockAgentCoreRuntimeRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all BedrockAgentCore Runtimes in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            paginator = proxy.get_paginator("list_agent_runtimes", "agentRuntimes")

            async for runtimes in paginator.paginate():
                if runtimes:
                    action_result = await inspector.inspect(
                        runtimes,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
