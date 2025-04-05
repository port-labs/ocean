from client import SonarQubeClient
from port_ocean.context.ocean import ocean


def init_sonar_client(metrics: list[str] = []) -> SonarQubeClient:
    return SonarQubeClient(
        ocean.integration_config.get("sonar_url", "https://sonarcloud.io"),
        ocean.integration_config["sonar_api_token"],
        ocean.integration_config.get("sonar_organization_id"),
        ocean.app.base_url,
        ocean.integration_config["sonar_is_on_premise"],
        metrics if metrics is not None else [],
    )
