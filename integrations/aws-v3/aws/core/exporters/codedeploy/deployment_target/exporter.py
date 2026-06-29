from typing import Any, AsyncGenerator, Type

from botocore.exceptions import ClientError
from loguru import logger

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codedeploy.deployment_target.actions import (
    CodeDeployDeploymentTargetActionsMap,
    DeploymentTargetActionInput,
)
from aws.core.exporters.codedeploy.deployment_target.models import (
    CodeDeployDeploymentTarget,
    SingleCodeDeployDeploymentTargetRequest,
    PaginatedCodeDeployDeploymentTargetRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodeDeployDeploymentTargetExporter(
    IResourceExporter[DeploymentTargetActionInput]
):
    _max_batch_size: int = 25
    _service_name: SupportedServices = "codedeploy"
    _model_cls: Type[CodeDeployDeploymentTarget] = CodeDeployDeploymentTarget
    _actions_map: Type[CodeDeployDeploymentTargetActionsMap] = (
        CodeDeployDeploymentTargetActionsMap
    )

    async def get_resource(
        self, options: SingleCodeDeployDeploymentTargetRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single CodeDeploy deployment target."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                DeploymentTargetActionInput(
                    deployment_id=options.deployment_id,
                    items=[options.target_id],
                ),
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedCodeDeployDeploymentTargetRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all CodeDeploy deployment targets in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            deployment_paginator = proxy.get_paginator(
                "list_deployments", "deployments"
            )
            target_paginator = proxy.get_paginator(
                "list_deployment_targets", "targetIds"
            )

            async for deployment_ids in deployment_paginator.paginate():
                for deployment_id in deployment_ids:
                    try:
                        async for target_ids in target_paginator.paginate(
                            deploymentId=deployment_id, batch_size=self._max_batch_size
                        ):
                            yield await inspector.inspect(
                                DeploymentTargetActionInput(
                                    deployment_id=deployment_id,
                                    items=target_ids,
                                ),
                                options.include,
                                extra_context={
                                    "AccountId": options.account_id,
                                    "Region": options.region,
                                },
                            )
                    except ClientError as e:
                        if (
                            e.response.get("Error", {}).get("Code")
                            == "DeploymentNotStartedException"
                        ):
                            logger.warning(
                                f"Deployment {deployment_id} has not started, unable to fetch targets."
                            )
                            continue
                        raise
