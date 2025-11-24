import asyncio

from port_ocean.run import run_integration


async def main():
    await run_integration()


if __name__ == "__main__":
    asyncio.run(main())