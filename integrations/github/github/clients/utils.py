from typing import Any, Dict
from port_ocean.context.ocean import ocean

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator


def integration_config(authenticator: AbstractGitHubAuthenticator) -> Dict[str, Any]:
    return {
        "authenticator": authenticator,
        "organization": ocean.integration_config["github_organization"],
        "github_host": ocean.integration_config["github_host"],
    }
