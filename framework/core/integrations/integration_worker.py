import importlib.util
from framework.config.config import settings
from framework.port.port import PortClient


class IntegrationWorker:
    def __init__(self, integraiton_type: str, integration_identifier: str, config: dict):
        self.integration_type = integraiton_type
        self.integration_identifier = integration_identifier
        self.config = config
        self.integration = None

    def _load_integration(self):
        spec = importlib.util.spec_from_file_location(
            "integration", f"integrations/{self.integration_type}/main.py"
        )
        integration = importlib.util.module_from_spec(spec)

        if spec.loader is None:
            raise Exception("Validate that the integration type is valid")

        spec.loader.exec_module(integration)

        return integration

    def init(self, trigger_channel: dict):
        self.integration = self._load_integration()
        self.port_client = PortClient(
            settings.PORT_CLIENT_ID, settings.PORT_CLIENT_SECRET, self.integration_identifier)

        self.port_client.initiate_integration(
            self.integration_identifier, self.integration_type, trigger_channel)

        self.integration.init(self.config)
