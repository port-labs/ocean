from port_ocean.context.integration import ocean
from port_ocean.types import ObjectDiff


@ocean.on_resync()
async def on_resync(kind: str) -> ObjectDiff:
    # Get all data from the source system
    # Return raw data to run manipulation over
    return {
        "before": [],
        "after": [
            {
                "id": "1",
                "name": "test",
                "http_url_to_repo": "http://test.com",
            }
        ],
    }


# Optional
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    print("Starting integration")


@ocean.router.post("/test")
async def a():
    await ocean.register_change([dict(a=1)])
    return dict(a=1)
