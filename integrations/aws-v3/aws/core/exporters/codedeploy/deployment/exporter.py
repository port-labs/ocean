from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codedeploy.deployment.actions import (
    CodeDeployDeploymentActionsMap,
)
from aws.core.exporters.codedeploy.deployment.models import CodeDeployDeployment
from aws.core.exporters.codedeploy.deployment.models import (
    SingleCodeDeployDeploymentRequest,
    PaginatedCodeDeployDeploymentRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodeDeployDeploymentExporter(IResourceExporter):
    _service_name: SupportedServices = "codedeploy"
    _model_cls: Type[CodeDeployDeployment] = CodeDeployDeployment
    _actions_map: Type[CodeDeployDeploymentActionsMap] = CodeDeployDeploymentActionsMap

    async def get_resource(
        self, options: SingleCodeDeployDeploymentRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single CodeDeploy deployment."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [{"deploymentId": options.deployment_id}],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedCodeDeployDeploymentRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all CodeDeploy deployments in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            paginator = proxy.get_paginator("list_deployments", "deployments")

            async for deployment_ids in paginator.paginate():
                if deployment_ids:
                    action_result = await inspector.inspect(
                        deployment_ids,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
