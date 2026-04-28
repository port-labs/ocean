from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.memorydb.user.actions import MemoryDbUserActionsMap
from aws.core.exporters.memorydb.user.models import (
    MemoryDbUser,
    PaginatedMemoryDbUserRequest,
    SingleMemoryDbUserRequest,
)
from aws.core.helpers.types import MEMORYDB_SUPPORTED_REGIONS, SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class MemoryDbUserExporter(IResourceExporter):
    _service_name: SupportedServices = "memorydb"
    _model_cls: Type[MemoryDbUser] = MemoryDbUser
    _actions_map: Type[MemoryDbUserActionsMap] = MemoryDbUserActionsMap
    _supported_regions: frozenset[str] = MEMORYDB_SUPPORTED_REGIONS

    async def get_resource(self, options: SingleMemoryDbUserRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single MemoryDB user."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await proxy.client.describe_users(UserName=options.user_name)  # type: ignore[attr-defined]
            users = response["Users"]
            action_result = await inspector.inspect(
                users,
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return action_result[0] if action_result else {}

    async def get_paginated_resources(
        self, options: PaginatedMemoryDbUserRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all MemoryDB users in the region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("describe_users", "Users")

            async for users in paginator.paginate():
                if users:
                    action_result = await inspector.inspect(
                        users,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
