# from port_ocean.context.ocean import ocean
# from spacelift.loader import SpaceliftLoader

# async def run():
#     loader = SpaceliftLoader(ocean)
#     await loader.run()

import os
print("PORT_CLIENT_ID in Python:", os.getenv("PORT_CLIENT_ID"))
print("PORT_CLIENT_SECRET in Python:", os.getenv("PORT_CLIENT_SECRET"))
print("PORT_BASE_URL in Python:", os.getenv("PORT_BASE_URL"))
import asyncio
from port_ocean.context.ocean import ocean
from .loader import SpaceliftLoader

@ocean.on_start()
async def run():
    loader = SpaceliftLoader(ocean)
    await loader.run()

if __name__ == "__main__":
    asyncio.run(ocean.run())




