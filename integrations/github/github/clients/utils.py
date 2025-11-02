from typing import Any, Dict, cast, TYPE_CHECKING
from github.core.options import ListOrganizationOptions
from github.helpers.exceptions import OrganizationRequiredException
from port_ocean.context.ocean import ocean

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from port_ocean.context.event import event

if TYPE_CHECKING:
    from integration import GithubPortAppConfig


def integration_config(authenticator: AbstractGitHubAuthenticator) -> Dict[str, Any]:
    return {
        "authenticator": authenticator,
        "github_host": ocean.integration_config["github_host"],
    }


def get_github_organizations() -> ListOrganizationOptions:
    """Get the organizations from the integration config."""
    organization = ocean.integration_config["github_organization"]
    port_app_config = cast("GithubPortAppConfig", event.port_app_config)

    return ListOrganizationOptions(
        organization=organization,
        allowed_multi_organizations=port_app_config.organizations,
    )


def get_mono_repo_organization(organization: str | None) -> str:
    """Get the organization for a monorepo."""
    organization = organization or ocean.integration_config["github_organization"]
    if not organization:
        raise OrganizationRequiredException("Organization is required")
    return organization
