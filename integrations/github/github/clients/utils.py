from typing import Any, Dict, List
from port_ocean.context.ocean import ocean

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator


def integration_config(authenticator: AbstractGitHubAuthenticator) -> Dict[str, Any]:
    return {
        "authenticator": authenticator,
        "github_host": ocean.integration_config["github_host"],
    }


def get_github_organizations() -> List[str]:
    """Get the organizations from the integration config."""
    return ocean.integration_config["github_organizations"]
