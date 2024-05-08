import typing
from aws.override import AWSPortAppConfig, AWSResourceConfig
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


def get_matching_kinds_from_config(
    kind: str,
) -> list[ResourceConfig | AWSResourceConfig]:
    result: list[ResourceConfig | AWSResourceConfig] = []
    kinds_cache: list[str] = []
    resources = typing.cast(AWSPortAppConfig, event.port_app_config).resources

    for resource in resources:
        if resource.kind in kinds_cache:
            continue
        if (
            isinstance(resource, AWSResourceConfig)
            and kind in resource.selector.resource_kinds
        ) or kind == resource.kind:
            result.append(resource)
            kinds_cache.append(resource.kind)

    return result
