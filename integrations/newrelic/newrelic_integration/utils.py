import typing

import jinja2
from port_ocean.context.event import event

from newrelic_integration.overrides import NewRelicPortAppConfig, NewRelicResourceConfig


async def get_port_resource_configuration_by_port_kind(
    kind: str,
) -> NewRelicResourceConfig | None:
    """
    This function is used to get the port resource configuration by the given kind.
    """
    app_config = typing.cast(NewRelicPortAppConfig, event.port_app_config)
    for resource in app_config.resources:
        if resource.kind == kind:
            return resource
    raise ValueError(f"Resource configuration not found for kind {kind}")


async def get_port_resource_configuration_by_newrelic_entity_type(
    entity_type: str,
) -> NewRelicResourceConfig | None:
    app_config = typing.cast(NewRelicPortAppConfig, event.port_app_config)
    for resource in app_config.resources:
        if (
            resource.selector.newrelic_types
            and entity_type in resource.selector.newrelic_types
        ):
            return resource
    return None


async def render_query(query_template: str, **kwargs: typing.Any) -> str:
    template = jinja2.Template(query_template, enable_async=True)
    return await template.render_async(
        **kwargs,
    )
