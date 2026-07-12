from typing import Any, Dict, cast, TYPE_CHECKING

from github.core.options import ListOrganizationOptions
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator

if TYPE_CHECKING:
    from integration import GithubPortAppConfig


def integration_config(authenticator: AbstractGitHubAuthenticator) -> Dict[str, Any]:
    return {
        "authenticator": authenticator,
        "github_host": ocean.integration_config["github_host"],
    }


def get_github_organizations(
    organization: str | None = None,
) -> ListOrganizationOptions:
    """Get the organizations from the integration config."""
    resolved_org = organization or ocean.integration_config.get("github_organization")
    port_app_config = cast("GithubPortAppConfig", event.port_app_config)

    options: ListOrganizationOptions = {
        "allowed_multi_organizations": port_app_config.organizations,
        "include_authenticated_user": port_app_config.include_authenticated_user,
    }
    if resolved_org:
        options["organization"] = resolved_org
    return options


def get_mono_repo_organization(organization: str | None) -> str | None:
    """Get the organization for a monorepo."""
    return organization or ocean.integration_config["github_organization"]
