from typing import Any, Dict
from github.core.options import ListOrganizationOptions
from github.helpers.exceptions import OrganizationRequiredException
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


def get_mono_repo_organization(organization: str | None) -> str:
    """Get the organization for a monorepo."""
    organization = organization or ocean.integration_config["github_organization"]
    if not organization:
        raise OrganizationRequiredException("Organization is required")
    return organization
