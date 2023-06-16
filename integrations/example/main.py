from port_ocean.context.integration import ocean
from port_ocean.types import ObjectDiff


@ocean.on_resync()
async def resync(kind: str) -> ObjectDiff:
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


@ocean.on_start()
async def start():
    print("start")


@ocean.router.post("/test")
async def a():
    await ocean.register_change([dict(a=1)])
    return dict(a=1)
