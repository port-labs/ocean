import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from coralogix.clients.client_factory import ClientFactory

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

TEST_INTEGRATION_CONFIG: dict[str, Any] = {
    "coralogix_api_key": "cxup_test",
    "coralogix_api_url": "https://myteam.app.eu2.coralogix.com",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_app = MagicMock()
        mock_app.integration_config = TEST_INTEGRATION_CONFIG
        mock_app.config.integration.config = TEST_INTEGRATION_CONFIG
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass

    ClientFactory.clear()


def load_example(kind: str, name: str = "a.json") -> dict[str, Any]:
    return json.loads((EXAMPLES_DIR / kind / name).read_text())


TEAM_IDENTITY = {
    "teamId": 4020299,
    "teamName": "getport",
    "teamUrl": "https://getport.app.eu2.coralogix.com",
    "username": "someone@example.com",
}
TEAM_URL = "https://getport.app.eu2.coralogix.com"


def strip_team(item: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in item.items() if k != "__teamUrl"}
