from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ses.email_identity.actions import SesEmailIdentityActionsMap
from aws.core.exporters.ses.email_identity.models import EmailIdentity
from aws.core.exporters.ses.email_identity.models import (
    SingleEmailIdentityRequest,
    PaginatedEmailIdentityRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class SesEmailIdentityExporter(IResourceExporter[list[dict[str, Any]]]):
    _service_name: SupportedServices = "sesv2"
    _model_cls: Type[EmailIdentity] = EmailIdentity
    _actions_map: Type[SesEmailIdentityActionsMap] = SesEmailIdentityActionsMap

    async def get_resource(
        self, options: SingleEmailIdentityRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single SES email identity."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            response = await proxy.client.get_email_identity(  # type: ignore[attr-defined]
                EmailIdentity=options.email_identity
            )
            identity = {"EmailIdentity": options.email_identity, **response}
            result = await inspector.inspect(
                [identity],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return result[0] if result else {}

    async def get_paginated_resources(
        self, options: PaginatedEmailIdentityRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all SES email identities in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            paginator = proxy.get_paginator(
                "list_email_identities", "EmailIdentities"
            )

            async for identities in paginator.paginate():
                if identities:
                    action_result = await inspector.inspect(
                        identities,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
