from client import DatadogClient
from port_ocean.context.ocean import ocean


def init_client() -> DatadogClient:
    return DatadogClient(
        ocean.integration_config["datadog_base_url"],
        ocean.integration_config["datadog_api_key"],
        ocean.integration_config["datadog_application_key"],
        ocean.integration_config["datadog_access_token"],
    )
