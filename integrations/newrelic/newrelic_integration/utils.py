import typing

import jinja2
from port_ocean.context.event import event

from newrelic_integration.overrides import NewRelicPortAppConfig


async def get_port_resource_configuration_by_port_kind(
    kind: str,
) -> typing.Dict[str, dict]:
    """
    This function is used to get the port resource configuration by the given kind.
    """
    app_config = typing.cast(NewRelicPortAppConfig, event.port_app_config)
    for resource in app_config.resources:
        if resource.kind == kind:
            return resource.dict()
    return {}


async def get_port_resource_configuration_by_newrelic_entity_type(
    entity_type: str,
) -> dict:
    app_config = typing.cast(NewRelicPortAppConfig, event.port_app_config)
    for resource in app_config.resources:
        if (
            resource.selector.newrelic_types
            and entity_type in resource.selector.newrelic_types
        ):
            return resource.dict()
    return {}


async def render_query(query_template: str, **kwargs) -> str:
    template = jinja2.Template(query_template, enable_async=True)
    return await template.render_async(
        **kwargs,
    )
