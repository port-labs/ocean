from typing import Any, AsyncGenerator, Type

from aiobotocore.config import AioConfig
from loguru import logger

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.cloudcontrol.resource.actions import (
    CloudControlActionInput,
    CloudControlActionsMap,
    CloudControlResourceIdentifier,
)
from aws.core.exporters.cloudcontrol.resource.models import (
    CloudControlResource,
    PaginatedCloudControlResourceRequest,
    SingleCloudControlResourceRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.helpers.utils import (
    is_cloud_control_type_unavailable_exception,
    parse_json_object_dict,
)
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector

CLOUD_CONTROL_CLIENT_CONFIG = AioConfig(
    retries={"mode": "adaptive", "max_attempts": 100}
)


class CloudControlExporter(IResourceExporter[CloudControlActionInput]):
    _service_name: SupportedServices = "cloudcontrol"
    _model_cls: Type[CloudControlResource] = CloudControlResource
    _actions_map: Type[CloudControlActionsMap] = CloudControlActionsMap

    def _proxy(self, region: str) -> AioBaseClientProxy:
        return AioBaseClientProxy(
            self.session,
            region,
            self._service_name,
            config=CLOUD_CONTROL_CLIENT_CONFIG,
        )

    def _inspector(
        self, client: Any, type_name: str
    ) -> ResourceInspector[CloudControlResource, CloudControlActionInput]:
        return ResourceInspector(
            client,
            self._actions_map(),
            lambda: self._model_cls(Type=type_name),
            action_id_key="Identifier",
        )

    async def get_resource(
        self, options: SingleCloudControlResourceRequest
    ) -> dict[str, Any]:
        async with self._proxy(options.region) as proxy:
            response = await proxy.client.get_resource(  # type: ignore[attr-defined]
                TypeName=options.type_name,
                Identifier=options.identifier,
            )
            description = response["ResourceDescription"]
            properties = parse_json_object_dict(description.get("Properties"))
            identifier = description.get("Identifier", options.identifier)

            inspector = self._inspector(proxy.client, options.type_name)
            result = await inspector.inspect(
                CloudControlActionInput(
                    items=[
                        CloudControlResourceIdentifier(
                            identifier=identifier,
                            properties=properties,
                        )
                    ],
                    type_name=options.type_name,
                ),
                [],
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return result[0] if result else {}

    async def get_paginated_resources(
        self, options: PaginatedCloudControlResourceRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        include = list(options.include)
        if options.use_get_resource_api:
            include.append("GetResourceAction")

        async with self._proxy(options.region) as proxy:
            inspector = self._inspector(proxy.client, options.type_name)
            paginator = proxy.get_paginator("list_resources", "ResourceDescriptions")
            try:
                async for resources in paginator.paginate(TypeName=options.type_name):
                    if not resources:
                        continue
                    items = [
                        CloudControlResourceIdentifier(
                            identifier=resource.get("Identifier", ""),
                            properties=parse_json_object_dict(
                                resource.get("Properties")
                            ),
                        )
                        for resource in resources
                        if resource.get("Identifier")
                    ]
                    yield await inspector.inspect(
                        CloudControlActionInput(
                            items=items,
                            type_name=options.type_name,
                        ),
                        include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
            except Exception as e:
                if is_cloud_control_type_unavailable_exception(e):
                    logger.warning(
                        f"Skipping Cloud Control type {options.type_name} in region "
                        f"{options.region} for account {options.account_id}: {e}"
                    )
                    return
                raise
