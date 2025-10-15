from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.organizations.account.actions import (
    OrganizationsAccountActionsMap,
)
from aws.core.exporters.organizations.account.models import Account
from aws.core.exporters.organizations.account.models import (
    SingleAccountRequest,
    PaginatedAccountRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class OrganizationsAccountExporter(IResourceExporter):
    _service_name: SupportedServices = "organizations"
    _model_cls: Type[Account] = Account
    _actions_map: Type[OrganizationsAccountActionsMap] = OrganizationsAccountActionsMap

    async def get_resource(self, options: SingleAccountRequest) -> dict[str, Any]:
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await inspector.inspect(
                [{"Id": options.account_id}], options.include
            )
            return response[0] if response else {}

    async def get_paginated_resources(
        self, options: PaginatedAccountRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            paginator = proxy.get_paginator("list_accounts", "Accounts")

            async for accounts in paginator.paginate():
                action_result = await inspector.inspect(accounts, options.include)
                yield action_result
