from client import SonarQubeClient
from port_ocean.context.ocean import ocean


def init_sonar_client() -> SonarQubeClient:
    return SonarQubeClient(
        ocean.integration_config.get("sonar_url", "https://sonarcloud.io"),
        ocean.integration_config["sonar_api_token"],
        ocean.integration_config.get("sonar_organization_id"),
        ocean.integration_config.get("app_host"),
        ocean.integration_config["sonar_is_on_premise"],
    )
