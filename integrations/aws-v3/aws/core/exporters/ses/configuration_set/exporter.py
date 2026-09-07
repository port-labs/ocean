from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ses.configuration_set.actions import (
    ConfigurationSetRecord,
    SesConfigurationSetActionsMap,
)
from aws.core.exporters.ses.configuration_set.models import ConfigurationSet
from aws.core.exporters.ses.configuration_set.models import (
    SingleConfigurationSetRequest,
    PaginatedConfigurationSetRequest,
)
from aws.core.exporters.ses.regions import SES_SUPPORTED_REGIONS
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class SesConfigurationSetExporter(IResourceExporter[list[ConfigurationSetRecord]]):
    _service_name: SupportedServices = "sesv2"
    _model_cls: Type[ConfigurationSet] = ConfigurationSet
    _actions_map: Type[SesConfigurationSetActionsMap] = SesConfigurationSetActionsMap
    _supported_regions: frozenset[str] = SES_SUPPORTED_REGIONS

    async def get_resource(
        self, options: SingleConfigurationSetRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single SES configuration set."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            # Live-event single-configuration-set fetch only has a name from CloudTrail.
            # GetConfigurationSetAction swallows recoverable not-found errors,
            # so the inspector would return an empty stub for a deleted set.
            # Confirm it exists so a missing set raises and the live-event handler
            # can treat the update as a delete instead.
            await proxy.client.get_configuration_set(  # type: ignore[attr-defined]
                ConfigurationSetName=options.configuration_set_name
            )

            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            result = await inspector.inspect(
                [
                    ConfigurationSetRecord(
                        ConfigurationSetName=options.configuration_set_name
                    )
                ],
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return result[0] if result else {}

    async def get_paginated_resources(
        self, options: PaginatedConfigurationSetRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all SES configuration sets in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            next_token: str | None = None
            while True:
                kwargs: dict[str, Any] = {"NextToken": next_token} if next_token else {}
                response = await proxy.client.list_configuration_sets(  # type: ignore[attr-defined]
                    **kwargs
                )
                configuration_set_names: list[str] = response.get(
                    "ConfigurationSets", []
                )
                configuration_sets: list[ConfigurationSetRecord] = [
                    ConfigurationSetRecord(ConfigurationSetName=name)
                    for name in configuration_set_names
                ]
                if configuration_sets:
                    action_result = await inspector.inspect(
                        configuration_sets,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []

                next_token = response.get("NextToken")
                if not next_token:
                    break
