#!/usr/bin/env python
import asyncio
from unittest.mock import MagicMock

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.ocean import Ocean
from port_ocean.tests.helpers.smoke_test import cleanup_smoke_test


async def main() -> None:
    # Clean script runs in a separate process; init minimal context (on-prem) so PortClient works.
    mock_ocean = MagicMock(spec=Ocean)
    mock_ocean.is_saas.return_value = False
    initialize_port_ocean_context(mock_ocean)

    await cleanup_smoke_test()


asyncio.get_event_loop().run_until_complete(main())
