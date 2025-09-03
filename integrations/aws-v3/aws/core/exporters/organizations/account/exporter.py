from typing import Any, AsyncGenerator, Type
from aws.core.exporters.organizations.account.actions import (
    OrganizationsAccountActionsMap,
)
from aws.core.exporters.organizations.account.models import (
    Account,
    SingleAccountRequest,
    PaginatedAccountRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from aws.core.client.proxy import AioBaseClientProxy


class OrganizationsAccountExporter(IResourceExporter):
    """
    Exporter for AWS Organizations accounts.

    Provides access to AWS account information from the Organizations service,
    with optional enrichment through include actions.
    """

    _service_name: SupportedServices = "organizations"
    _model_cls: Type[Account] = Account
    _actions_map: Type[OrganizationsAccountActionsMap] = OrganizationsAccountActionsMap

    async def get_resource(self, options: SingleAccountRequest) -> dict[str, Any]:
        """Fetch single account using the standard ResourceInspector pattern."""
        async with AioBaseClientProxy(self.session, None, self._service_name) as proxy:
            inspector = ResourceInspector(
                proxy.client,
                self._actions_map(),
                lambda: self._model_cls(),
                options.account_id,
                "",  # region is empty string for global services like Organizations
            )

            # Always call ResourceInspector (even if no actions)
            result = await inspector.inspect(options.account_id, options.include)

            # Always inject authentication data
            for key, value in options.account_data.items():
                setattr(result.Properties, key, value)

            return result.dict(exclude_none=True)

    async def get_paginated_resources(
        self, options: PaginatedAccountRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Accounts don't support pagination - use get_resource instead."""
        raise NotImplementedError(
            "Account discovery is performed by the authentication strategy."
        )
        yield
