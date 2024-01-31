from enum import StrEnum

from client import DatadogClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    HOST = "host"
    MONITOR = "monitor"
    SLO = "slo"


def init_client() -> DatadogClient:
    return DatadogClient(
        ocean.integration_config["datadog_base_url"],
        ocean.integration_config["datadog_api_key"],
        ocean.integration_config["datadog_application_key"],
    )


@ocean.on_resync()
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    if kind == ObjectKind.HOST:
        async for hosts in dd_client.get_hosts():
            yield hosts
    if kind == ObjectKind.MONITOR:
        async for monitors in dd_client.get_monitors():
            yield monitors
    if kind == ObjectKind.SLO:
        async for slos in dd_client.get_slos():
            yield slos
