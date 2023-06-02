from framework.config.config import settings
from framework.consumers.kafka_consumer import KafkaConsumer
from framework.common.resource_to_port_entity import resources_to_port_entity
from framework.core.integrations.integration_worker import IntegrationWorker
from framework.core.trigger_channel.trigger_channel_fcatory import TriggerChannelFactory


class IntegrationsOrchestrator:
    def __init__(self, config: dict):
        self.config = config

        self.trigger_channel = TriggerChannelFactory(config['triggerChannel']['type']).create_trigger_channel(
            self.on_action,
            self.on_changelog_event
        )

        self.integration_workers = []

    def on_changelog_event(self, event: dict):
        kinds = set()

        integration_configurations = event.get(
            "diff", {}).get("after", {})

        mappings = integration_configurations.get(
            "config", {}).get("resources", [])

        integration_worker_to_use = None

        for integration_worker in self.integration_workers:
            if integration_worker.integration_identifier == integration_configurations.get("identifier", ""):
                integration_worker_to_use = integration_worker
                break

        for mapping in mappings:
            kinds.add(mapping["kind"])

        raw_entities = integration_worker_to_use.integration.on_resync(
            kinds)

        for raw_entity in raw_entities:
            port_entity = resources_to_port_entity(
                raw_entity, mappings)

            self.port_client.upsert_entity(
                port_entity, integration_worker_to_use.integration_identifier)

    def on_action(self, action: dict):
        pass

    def start(self):
        integrations_from_config = self.config.get('integrations', [])

        for integration in integrations_from_config:
            # TODO: add validation that integration type is valid and exists
            integration_type = integration.get('type')
            integration_config = integration.get('config', {})
            integration_identifier = integration.get('identifier', '')
            integration_worker = IntegrationWorker(
                integration_type, integration_identifier, integration_config)
            integration_worker.init(self.config['triggerChannel'])
            self.integration_workers.append(integration_worker)

        self.trigger_channel.start()
