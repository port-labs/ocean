from typing import Any, Dict
from github.core.options import ListOrganizationOptions
from port_ocean.context.ocean import ocean

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator


def integration_config(authenticator: AbstractGitHubAuthenticator) -> Dict[str, Any]:
    return {
        "authenticator": authenticator,
        "github_host": ocean.integration_config["github_host"],
    }


def get_github_organizations() -> ListOrganizationOptions:
    """Get the organizations from the integration config."""
    organization = ocean.integration_config["github_organization"]
    multi_organizations = ocean.integration_config["github_multi_organizations"]
    return {
        "organization": organization,
        "multi_organizations": multi_organizations,
    }
