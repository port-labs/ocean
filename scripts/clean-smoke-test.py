#!/usr/bin/env python
import asyncio
from unittest.mock import MagicMock

from port_ocean.config.settings import SslSettings
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.ocean import Ocean
from port_ocean.tests.helpers.smoke_test import cleanup_smoke_test


def _create_minimal_ocean_mock() -> MagicMock:
    """Minimal Ocean context for standalone scripts that use PortClient."""
    mock_ocean = MagicMock(spec=Ocean)
    mock_ocean.is_saas.return_value = False
    mock_config = MagicMock()
    mock_config.ssl = SslSettings()
    mock_ocean.config = mock_config
    return mock_ocean


async def main() -> None:
    # Clean script runs in a separate process; init minimal context (on-prem) so PortClient works.
    initialize_port_ocean_context(_create_minimal_ocean_mock())

    await cleanup_smoke_test()


if __name__ == "__main__":
    asyncio.run(main())
