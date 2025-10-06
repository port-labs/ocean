from unittest.mock import MagicMock

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "azure_client_id": "123",
            "azure_client_secret": "secret",
            "azure_tenant_id": "123",
        }
        mock_ocean_app.config.resources = [
            {
                "kind": "resourceContainer",
                "selector": {
                    "query": "resources | where type =~ 'Microsoft.Resources/subscriptions/resourceGroups'",
                    "tags": {},
                },
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".name",
                            "title": ".name",
                            "blueprint": "'resourceGroup'",
                            "properties": {"tags": ".tags"},
                        }
                    }
                },
            },
            {
                "kind": "resource",
                "selector": {
                    "query": "resources",
                    "types": ["Microsoft.Compute/virtualMachines"],
                    "tags": {},
                },
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".id",
                            "title": ".name",
                            "blueprint": "'virtualMachine'",
                            "properties": {"tags": ".tags"},
                        }
                    }
                },
            },
        ]
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()

        # We also need to mock the integration class on the app, so that the correct AppConfigHandlerClass is used
        from integration import AzureIntegration

        mock_ocean_app.integration = AzureIntegration()

        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass
