from typing import Any, Dict, Optional, cast, TYPE_CHECKING
from github.core.options import ListOrganizationOptions, ListRepositoryOptions
from github.helpers.models import RepoSearchParams
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
        allow_personal_organization=port_app_config.allow_personal_organization,
    )


def get_mono_repo_organization(organization: str | None) -> str | None:
    """Get the organization for a monorepo."""
    return organization or ocean.integration_config["github_organization"]


def get_repository_options(
    organization: str,
    organization_type: str,
    search_params: Optional[RepoSearchParams] = None,
    included_relationships: Optional[list[str]] = None,
) -> ListRepositoryOptions:

    port_app_config = cast("GithubPortAppConfig", event.port_app_config)

    return ListRepositoryOptions(
        organization=organization,
        organization_type=organization_type,
        type=port_app_config.repository_type,
        search_params=search_params,
        included_relationships=included_relationships,
    )
