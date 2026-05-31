from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.codedeploy.application.actions import CodeDeployApplicationActionsMap
from aws.core.exporters.codedeploy.application.models import CodeDeployApplication
from aws.core.exporters.codedeploy.application.models import (
    SingleCodeDeployApplicationRequest,
    PaginatedCodeDeployApplicationRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class CodeDeployApplicationExporter(IResourceExporter):
    _service_name: SupportedServices = "codedeploy"
    _model_cls: Type[CodeDeployApplication] = CodeDeployApplication
    _actions_map: Type[CodeDeployApplicationActionsMap] = CodeDeployApplicationActionsMap

    async def get_resource(self, options: SingleCodeDeployApplicationRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single CodeDeploy application."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [{"ApplicationName": options.application_name}], options.include
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedCodeDeployApplicationRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all CodeDeploy applications in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # Use the list_applications API to get all applications
            paginator = proxy.get_paginator("list_applications", "applications")
            
            async for applications in paginator.paginate():
                if applications:
                    # Transform application names to the expected format
                    resources = [{"ApplicationName": app_name} for app_name in applications]
                    action_result = await inspector.inspect(
                        resources,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []