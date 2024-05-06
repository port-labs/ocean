import typing
from aws.overrides import AWSPortAppConfig, AWSResourceConfig
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


def get_matching_kinds_from_config(kind: str) -> list[ResourceConfig]:
    return list(
        filter(
            lambda resource_config: resource_config.kind == kind
            or (
                isinstance(resource_config, AWSResourceConfig)
                and kind in resource_config.selector.resource_kinds
            ),
            typing.cast(AWSPortAppConfig, event.port_app_config).resources,
        )
    )


def get_resource_kinds_from_config(kind: str) -> list[str]:
    """
    Gets the `resourceKinds` property from the port_app_config that match the given resource kind
    """
    resource_config = typing.cast(AWSResourceConfig, event.resource_config)
    resource_config
    if (
        resource_config.kind == kind
        and hasattr(resource_config.selector, "resource_kinds")
        and resource_config.selector.resource_kinds
    ):
        return resource_config.selector.resource_kinds
    return []
