from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ecs.task_definition.actions import EcsTaskDefinitionActionsMap
from aws.core.exporters.ecs.task_definition.models import TaskDefinition
from aws.core.exporters.ecs.task_definition.models import (
    SingleTaskDefinitionRequest,
    PaginatedTaskDefinitionRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class EcsTaskDefinitionExporter(IResourceExporter):
    _service_name: SupportedServices = "ecs"
    _model_cls: Type[TaskDefinition] = TaskDefinition
    _actions_map: Type[EcsTaskDefinitionActionsMap] = EcsTaskDefinitionActionsMap

    async def get_resource(
        self, options: SingleTaskDefinitionRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single ECS task definition."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [options.task_definition_arn],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )

            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedTaskDefinitionRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all active ECS task definitions in the region."""

        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator(
                "list_task_definitions", "taskDefinitionArns"
            )

            async for task_definition_arns in paginator.paginate(status="ACTIVE"):
                if task_definition_arns:
                    action_result = await inspector.inspect(
                        task_definition_arns,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
