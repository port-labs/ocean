from typing import Any, AsyncGenerator

from client import CloudFunctionClient
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client


# Required
# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync()
async def on_resync(kind: str) -> AsyncGenerator[list[dict[str, Any]], None]:
    port_client = ocean.integration.context.app.port_client
    agent = f"{port_client.integration_identifier}/{port_client.integration_version}"
    function_url = ocean.integration_config["function_url"]
    secrets = ocean.integration_config.get("secrets", {})

    client = CloudFunctionClient(
        agent=agent,
        http_client=http_async_client,
        function_url=function_url,
        secrets=secrets,
    )
    async for data in client.sync(kind):
        yield data


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting cloud_function integration")
