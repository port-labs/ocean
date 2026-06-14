from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codedeploy.deployment_group.actions import (
    CodeDeployDeploymentGroupActionsMap,
    DeploymentGroupActionInput,
)
from aws.core.exporters.codedeploy.deployment_group.models import (
    CodeDeployDeploymentGroup,
)
from aws.core.exporters.codedeploy.deployment_group.models import (
    SingleCodeDeployDeploymentGroupRequest,
    PaginatedCodeDeployDeploymentGroupRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodeDeployDeploymentGroupExporter(IResourceExporter):
    _service_name: SupportedServices = "codedeploy"
    _model_cls: Type[CodeDeployDeploymentGroup] = CodeDeployDeploymentGroup
    _actions_map: Type[CodeDeployDeploymentGroupActionsMap] = (
        CodeDeployDeploymentGroupActionsMap
    )

    async def get_resource(
        self, options: SingleCodeDeployDeploymentGroupRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single CodeDeploy deployment group."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            response = await inspector.inspect(
                DeploymentGroupActionInput(
                    app_name=options.application_name,
                    groups=[options.deployment_group_name],
                    region=options.region,
                    account_id=options.account_id,
                ),
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedCodeDeployDeploymentGroupRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all CodeDeploy deployment groups in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            # CodeDeploy doesn't have a direct paginator for deployment groups
            # We need to first list applications, then list deployment groups for each application
            app_paginator = proxy.get_paginator("list_applications", "applications")
            group_paginator = proxy.get_paginator(
                "list_deployment_groups", "deploymentGroups"
            )

            async for application_names in app_paginator.paginate():
                for app in application_names:
                    async for groups in group_paginator.paginate(applicationName=app):
                        yield (
                            await inspector.inspect(
                                DeploymentGroupActionInput(
                                    app_name=app,
                                    groups=groups,
                                    region=options.region,
                                    account_id=options.account_id,
                                ),
                                options.include,
                                extra_context={
                                    "AccountId": options.account_id,
                                    "Region": options.region,
                                },
                            )
                            if groups
                            else []
                        )
