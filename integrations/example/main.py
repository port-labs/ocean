from port_ocean.context.integration import ocean


@ocean.on_resync()
async def resync(kind: str):
    return []


@ocean.on_start()
async def start():
    print("start")


@ocean.router.post("/test")
async def a():
    await ocean.register_change([dict(a=1)])
    return dict(a=1)
