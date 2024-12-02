from typing import Any, cast

import httpx
import jinja2
from loguru import logger
from port_ocean.context.ocean import ocean


async def render_query(query_template: str, **kwargs: Any) -> str:
    """
    This function is used to render the query template with the given kwargs.
    :param query_template: The query template to render.
    :param kwargs: The kwargs to pass to the query template.
    :return: The rendered query.
    """
    template = jinja2.Template(query_template, enable_async=True)
    return await template.render_async(
        **kwargs,
    )


async def send_graph_api_request(
    async_client: httpx.AsyncClient, query: str, **log_fields: Any
) -> Any:
    logger.debug("Sending graph api request", **log_fields)
    api_url = cast(str, ocean.integration_config.get("new_relic_graphql_url"))
    new_relic_api_key = cast(str, ocean.integration_config.get("new_relic_api_key"))
    response = await async_client.post(
        api_url,
        headers={
            "Content-Type": "application/json",
            "API-Key": new_relic_api_key,
        },
        json={"query": query},
    )
    logger.debug("Received graph api response", **log_fields)
    response.raise_for_status()
    return response.json()


def format_tags(entity: dict[Any, Any]) -> dict[Any, Any]:
    entity["tags"] = {tag["key"]: tag["values"] for tag in entity.get("tags", [])}
    return entity
