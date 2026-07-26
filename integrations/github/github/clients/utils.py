from typing import Any, Dict

from port_ocean.context.ocean import ocean

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator


def integration_config(authenticator: AbstractGitHubAuthenticator) -> Dict[str, Any]:
    return {
        "authenticator": authenticator,
        "github_host": ocean.integration_config["github_host"],
    }


def can_access_organization(
    authenticator: AbstractGitHubAuthenticator, organization: str | None
) -> bool:
    return (
        authenticator.organization is None
        or organization is None
        or organization.casefold() == authenticator.organization.casefold()
    )
