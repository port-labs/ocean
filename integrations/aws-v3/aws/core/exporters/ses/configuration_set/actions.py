from typing import Any, NotRequired, Type, TypedDict
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class ConfigurationSetRecord(TypedDict):
    """Configuration set record that actions operate on.

    ``ConfigurationSetName`` is always present, whether sourced from a single
    ``get_resource`` call or from a ``list_configuration_sets`` page.
    """

    ConfigurationSetName: str
    TrackingOptions: NotRequired[dict[str, Any]]
    DeliveryOptions: NotRequired[dict[str, Any]]
    ReputationOptions: NotRequired[dict[str, Any]]
    SendingOptions: NotRequired[dict[str, Any]]
    Tags: NotRequired[list[dict[str, str]]]
    SuppressionOptions: NotRequired[dict[str, Any]]
    VdmOptions: NotRequired[dict[str, Any]]
    ArchivingOptions: NotRequired[dict[str, Any]]


class GetConfigurationSetAction(Action[list[ConfigurationSetRecord]]):
    """Fetches detailed information for SES configuration sets."""

    async def _execute(
        self, configuration_sets: list[ConfigurationSetRecord]
    ) -> list[dict[str, Any]]:
        return await execute_concurrent_aws_operations(
            input_items=configuration_sets,
            operation_func=self._fetch_configuration_set,
            get_resource_identifier=lambda cs: cs.get(
                "ConfigurationSetName", "unknown"
            ),
            operation_name="configuration set details",
        )

    async def _fetch_configuration_set(
        self, configuration_set: ConfigurationSetRecord
    ) -> dict[str, Any]:
        response = await self.client.get_configuration_set(
            ConfigurationSetName=configuration_set["ConfigurationSetName"]
        )
        response.pop("ResponseMetadata", None)
        return response


class ListConfigurationSetsAction(Action[list[ConfigurationSetRecord]]):
    """Processes the initial list of configuration sets from AWS."""

    async def _execute(
        self, configuration_sets: list[ConfigurationSetRecord]
    ) -> list[dict[str, Any]]:
        """Return configuration sets as-is from the list response."""
        return configuration_sets  # type: ignore[return-value]


class SesConfigurationSetActionsMap(ActionMap[list[ConfigurationSetRecord]]):
    """Groups all actions for SES configuration sets."""

    defaults: list[Type[Action[list[ConfigurationSetRecord]]]] = [
        ListConfigurationSetsAction,
        GetConfigurationSetAction,
    ]
    options: list[Type[Action[list[ConfigurationSetRecord]]]] = []
