from typing import List, Dict, Any

from port_ocean.context.ocean import ocean


@ocean.on_resync()
async def on_resync(kind: str) -> List[Dict[Any, Any]]:
    # Get all data from the source system
    # Return raw data to run manipulation over
    return [
        {
            "id": str(i),
            "name": "test",
            "http_url_to_repo": "http://test.com",
        }
        for i in range(300)
    ]


# Optional
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    print("Starting integration")


@ocean.router.post("/test")
async def a():
    await ocean.sync_raw("a", [dict(a=1)])
    return dict(a=1)
