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
from aws.core.modeling.resource_builder import ResourceBuilder


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
        """Fetch single account using the provided account data."""
        builder: Any = ResourceBuilder(self._model_cls(), account_id=options.account_id)

        properties_data: list[Any] = [options.account_data]

        if options.include:
            async with self.session.create_client(
                "organizations", region_name=None
            ) as client:
                inspector = ResourceInspector(
                    client,
                    self._actions_map(),
                    lambda: self._model_cls(),
                    account_id=options.account_id,
                )

                enriched_model = await inspector.inspect(
                    options.account_id, options.include
                )

                action_properties = enriched_model.Properties.dict(exclude_none=True)

                if action_properties:
                    properties_data.append(action_properties)

        builder.with_properties(properties_data)
        account_model = builder.build()

        return account_model.dict(exclude_none=True)

    async def get_paginated_resources(
        self, options: PaginatedAccountRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Accounts don't support pagination - use get_resource instead."""
        raise NotImplementedError(
            "Account resources don't support pagination. Use get_resource() instead."
        )
        yield
