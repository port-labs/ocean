import enum
import typing
from aws.override import AWSPortAppConfig, AWSResourceConfig
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


class CustomProperties(enum.StrEnum):
    ACCOUNT_ID = "__AccountId"
    KIND = "__Kind"
    REGION = "__Region"


class ResourceKinds(enum.StrEnum):
    ACCOUNT = "AWS::Organizations::Account"
    CLOUD_CONTROL_RESOURCE = "cloudResource"


def get_matching_kinds_and_blueprints_from_config(
    kind: str,
) -> dict[str, list[str]]:
    kinds: dict[str, list[str]] = {}
    resources = typing.cast(AWSPortAppConfig, event.port_app_config).resources

    for resource in resources:
        blueprint = resource.port.entity.mappings.blueprint.strip('"')
        if resource.kind in kinds:
            kinds[resource.kind].append(blueprint)
        elif (
            isinstance(resource, AWSResourceConfig)
            and kind in resource.selector.resource_kinds
        ) or kind == resource.kind:
            kinds[resource.kind] = [blueprint]

    return kinds
