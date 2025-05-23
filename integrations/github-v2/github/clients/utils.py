from typing import Any, Dict
from port_ocean.context.ocean import ocean


def integration_config() -> Dict[str, Any]:
    return {
        "token": ocean.integration_config["github_token"],
        "organization": ocean.integration_config["github_organization"],
        "github_host": ocean.integration_config["github_host"],
    }
