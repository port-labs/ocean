from typing import Any

from port_ocean.context.ocean import ocean


@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    # Get all data from the source system
    # Return raw data to run manipulation over
    return []


# Optional
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    print("Starting integration")
