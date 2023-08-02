import httpx
import jinja2
from loguru import logger
from port_ocean.context.ocean import ocean


async def render_query(query_template: str, **kwargs) -> str:
    template = jinja2.Template(query_template, enable_async=True)
    return await template.render_async(
        **kwargs,
    )


async def send_graph_api_request(query: str, **log_fields) -> dict:
    async with httpx.AsyncClient() as client:
        logger.debug("Sending graph api request", **log_fields)
        response = await client.post(
            ocean.integration_config.get("new_relic_graphql_apiurl"),
            headers={
                "Content-Type": "application/json",
                "API-Key": ocean.integration_config.get("new_relic_api_key"),
            },
            json={"query": query},
        )
        logger.debug("Received graph api response", **log_fields)
        response.raise_for_status()
        return response.json()
