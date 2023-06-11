from port_ocean.context.integration import ocean


@ocean.on_resync()
async def on_resync(kind: str):
    # Get all data from the source system
    # Return raw data to run manipulation over
    return []


# Optional
@ocean.on_start()
async def on_start():
    # Something to do when the integration starts
    print("Starting integration")
