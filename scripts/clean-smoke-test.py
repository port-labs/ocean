#!/usr/bin/env python
import asyncio
from port_ocean.tests.helpers.smoke_test import cleanup_smoke_test


async def main() -> None:
    await cleanup_smoke_test()


asyncio.get_event_loop().run_until_complete(main())
