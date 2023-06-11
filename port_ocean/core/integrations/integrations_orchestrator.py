from port_ocean.config.config import settings
from port_ocean.common.resource_to_port_entity import resources_to_port_entity
from port_ocean.core.integrations.integration_worker import IntegrationWorker
from port_ocean.core.trigger_channel.trigger_channel_factory import (
    TriggerChannelFactory,
)
from port_ocean.core.port.port import PortClient


class IntegrationsOrchestrator:
    def __init__(self, config: dict):
        self.config = config

        self.trigger_channel = TriggerChannelFactory(
            config["triggerChannel"]["type"]
        ).create_trigger_channel(self.on_action, self.on_changelog_event)

        self.integration_workers = []

    def on_changelog_event(self, event: dict):
        kinds = set()

        integration_configurations = event.get("diff", {}).get("after", {})

        mappings = integration_configurations.get("config", {}).get("resources", [])

        integration_worker_to_use = None

        for integration_worker in self.integration_workers:
            if (
                integration_worker.integration_identifier
                == integration_configurations.get("identifier", "")
            ):
                integration_worker_to_use = integration_worker
                break

        for mapping in mappings:
            raw_entities = integration_worker_to_use.integration.on_resync(
                mapping["kind"]
            )

            port_client = PortClient(
                settings.PORT_CLIENT_ID,
                settings.PORT_CLIENT_SECRET,
                integration_worker.integration_identifier,
            )

            for raw_entity in raw_entities:
                port_entity = resources_to_port_entity(raw_entity, mapping)
                port_client._upsert_entity(port_entity)

    def on_action(self, action: dict):
        pass

    def start(self):
        integrations_from_config = self.config.get("integrations", [])

        for integration_config in integrations_from_config:
            integration_worker = IntegrationWorker(
                integration_config.get("type"),
                integration_config.get("identifier", ""),
                integration_config.get("config", {}),
            )

            integration_worker.init(self.config["triggerChannel"])

            self.integration_workers.append(integration_worker)

        self.trigger_channel.trigger_start()
