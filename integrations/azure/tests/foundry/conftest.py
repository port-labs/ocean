import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from azure_integration.foundry.helpers.project_scope import project_endpoint_context

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_PROJECT_ENDPOINT = "https://acct.services.ai.azure.com/api/projects/demo"
TEST_PROJECT_ARM_ID = (
    "/subscriptions/sub/resourceGroups/rg/providers/"
    "Microsoft.CognitiveServices/accounts/acct/projects/demo"
)

TEST_INTEGRATION_CONFIG: dict[str, Any] = {
    "azure_tenant_id": "tenant",
    "azure_client_id": "client",
    "azure_client_secret": "secret",
    "api_version": "v1",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = TEST_INTEGRATION_CONFIG
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = "https://example.com"
        mock_ocean_app.config.event_listener.should_process_webhooks = True
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass
    ocean.integration_config.update(TEST_INTEGRATION_CONFIG)


@pytest.fixture(autouse=True)
def foundry_project_context():
    with project_endpoint_context(
        TEST_PROJECT_ENDPOINT, project_arm_id=TEST_PROJECT_ARM_ID
    ) as endpoint:
        yield endpoint
