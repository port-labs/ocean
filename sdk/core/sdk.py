import importlib.util
import json
from sdk.config.config import settings

from sdk.consumers.kafka import KafkaConsumer
from sdk.core.resource_to_port_entity import resources_to_port_entity
from sdk.port.port import PortClient

class SDK:
    def __init__(self, integration_type: str, integration_identifier: str):
        self.integration_type = integration_type
        self.integration_identifier = integration_identifier
        self.integration = None

    def _load_integration(self):
        spec = importlib.util.spec_from_file_location(
            "integration", f"integrations/{self.integration_type}/main.py"
        )
        integration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(integration)

        return integration

    def should_be_processed(msg_value: dict, topic: str) -> dict:
        if 'runs' in topic:
            return msg_value.get("payload", {}).get("action", {}).get("invocationMethod", {}).get("type", "") == "KAFKA"
            

        if 'change.log' in topic:
            return msg_value.get("changelogDestination", {}).get("type", "") == "KAFKA"
            
        return False

    def _handle_message(self, raW_msg):
        message = json.loads(raW_msg.value().decode())
        topic = raW_msg.topic()

        if not self.should_be_processed(message, topic):
            return
        
        integration_configurations = message.get("context", {}).get("integration", {})

        if integration_configurations.get("identifier", "") == self.integration_identifier:
           kinds = set()
           resources_mappings = integration_configurations.get("config", {}).get("resources", [])

           for resource in resources_mappings:
                kinds.add(resource["kind"])

           raw_entities = self.integration.on_resync(kinds)
           selector = self.resource_config.get('selector', {})
           self.selector_query = selector.get('query')
           
           for raw_entity in raw_entities:
               port_entity = resources_to_port_entity(raw_entity, resources_mappings)
               


    def init(self):
        self.integration = self._load_integration()
        port_client = PortClient(settings.PORT_CLIENT_ID, settings.PORT_CLIENT_SECRET, self.integration_identifier).initiate_integration(self.integration_identifier)

        kafka_creds = port_client.get_kafka_creds()['credentials']
        org_id = port_client.get_org_id()


        self.integration.init()

        # starting kafka consumer
        KafkaConsumer(msg_process=self._handle_message, org_id=org_id, kafka_creds=kafka_creds).start()
    