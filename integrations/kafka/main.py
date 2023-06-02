from kafka.admin import KafkaAdminClient, ConfigResource, ConfigResourceType

configuration = {}
admin_client = None


class Integration:
    def __init__(self, configuration: dict):
        self.configuration = configuration
        self.admin_client = KafkaAdminClient(**configuration)

    def fetch_topics(self):
        topic_list = self.admin_client.list_topics()
        topics = self.admin_client.describe_topics(topics=topic_list)
        topics_configurations = self.admin_client.describe_configs(config_resources=[
            ConfigResource(ConfigResourceType.TOPIC, topic) for topic in topic_list])

        for topic in topics:
            topics_configurations = topics_configurations[0]
            for resource in topics_configurations.resources:
                if topic["topic"] == resource[3]:
                    topic["config"] = resource[4].to_list()
                    break
        return topics

    def on_resync(self, kind: str):
        if kind == 'topics':
            return self.fetch_topics()

        return []

    def on_action_invoked(type, configuration_mapping):
        # Handle the on_action_invoked event
        # Example implementation:
        # - Perform actions based on the type and configuration_mapping
        # - No need to consume Kafka message here
        pass
