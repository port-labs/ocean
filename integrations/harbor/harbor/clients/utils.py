from harbor.clients.auth.abstract_authenticator import AbstractHarborAuthenticator
from port_ocean.context.ocean import ocean
from typing import Dict, Any


def integration_config(authenticator: AbstractHarborAuthenticator) -> Dict[str, Any]:
    return {
        "authenticator": authenticator,
        "harbor_host": ocean.integration_config["harbor_host"],
        "username": ocean.integration_config["username"],
        "password": ocean.integration_config["password"],
        "robot_name": ocean.integration_config["robot_name"],
        "robot_token": ocean.integration_config["robot_token"],
    }
