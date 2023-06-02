def fetch_resources(kind_list: list):
    return []


def init(configuration):
    # Initialize the integration based on the provided configuration
    # Example implementation:
    # - Set up webhooks
    # - Store configuration
    pass


def on_resync(kind_list: list[str]):
    # Handle the on_resync event
    # Example implementation:
    # - Fetch all resources of the specified kinds
    # - Pass the resources to the provided handler function for further processing
    resources = fetch_resources(kind_list)
    return resources


def on_action_invoked(type, configuration_mapping):
    # Handle the on_action_invoked event
    # Example implementation:
    # - Perform actions based on the type and configuration_mapping
    # - No need to consume Kafka message here
    pass
