import yaml
from port_ocean.config.settings import IntegrationConfiguration


def load_integration_config_from_file(
    integration_config: IntegrationConfiguration,
) -> IntegrationConfiguration:
    try:
        config_file_path = integration_config.config_file_path
        if config_file_path is None:
            return integration_config
        with open(config_file_path, "r") as f:
            file_config = yaml.safe_load(f)
        return IntegrationConfiguration(**integration_config.dict(), **file_config)
    except Exception as e:
        raise ValueError(f"Failed to load configuration from file: {e}")
