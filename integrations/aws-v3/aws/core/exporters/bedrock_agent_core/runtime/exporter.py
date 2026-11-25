from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.bedrock_agent_core.runtime.actions import (
    BedrockAgentCoreRuntimeActionsMap,
)
from aws.core.exporters.bedrock_agent_core.runtime.models import (
    BedrockAgentCoreRuntime,
    PaginatedBedrockAgentCoreRuntimeRequest,
    SingleBedrockAgentCoreRuntimeRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class BedrockAgentCoreRuntimeExporter(IResourceExporter[list[dict[str, Any]]]):
    _service_name: SupportedServices = "bedrock-agentcore-control"
    _model_cls: Type[BedrockAgentCoreRuntime] = BedrockAgentCoreRuntime
    _actions_map: Type[
        BedrockAgentCoreRuntimeActionsMap
    ] = BedrockAgentCoreRuntimeActionsMap

    async def get_resource(
        self, options: SingleBedrockAgentCoreRuntimeRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single BedrockAgentCore Runtime."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [{"agentRuntimeId": options.agent_runtime_id}],
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
