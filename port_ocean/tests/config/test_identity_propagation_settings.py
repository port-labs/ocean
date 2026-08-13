import pytest
from pydantic.v1 import ValidationError

from port_ocean.config.settings import (
    AzureDevOpsOAuthSettings,
    GitHubOAuthSettings,
    GitLabOAuthSettings,
    IdentityPropagationOAuthSettings,
    IdentityPropagationSettings,
)


def test_identity_propagation_is_disabled_by_default() -> None:
    settings = IdentityPropagationSettings()

    assert settings.enabled is False
    assert settings.vault.secret_prefix == "port/tokens"
    assert settings.oauth.github is None
    assert settings.oauth.gitlab is None
    assert settings.oauth.azure_devops is None


def test_a_target_can_be_configured_on_its_own() -> None:
    settings = IdentityPropagationOAuthSettings(
        github=GitHubOAuthSettings(client_id="id", client_secret="secret")
    )

    assert settings.github is not None
    assert settings.github.client_id == "id"
    assert settings.gitlab is None


def test_gitlab_accepts_a_custom_host() -> None:
    settings = IdentityPropagationOAuthSettings(
        gitlab=GitLabOAuthSettings(
            client_id="id", client_secret="secret", host="https://gitlab.acme.com"
        )
    )

    assert settings.gitlab is not None
    assert settings.gitlab.host == "https://gitlab.acme.com"


def test_azure_devops_requires_a_tenant_id() -> None:
    with pytest.raises(ValidationError, match="tenant_id"):
        IdentityPropagationOAuthSettings(
            azure_devops=AzureDevOpsOAuthSettings(client_id="id", client_secret="secret")  # type: ignore[call-arg]
        )


def test_azure_devops_accepts_a_tenant_id() -> None:
    settings = IdentityPropagationOAuthSettings(
        azure_devops=AzureDevOpsOAuthSettings(
            client_id="id", client_secret="secret", tenant_id="tenant-1"
        )
    )

    assert settings.azure_devops is not None
    assert settings.azure_devops.tenant_id == "tenant-1"


def test_oauth_credentials_are_marked_sensitive() -> None:
    settings = IdentityPropagationSettings(
        enabled=True,
        oauth=IdentityPropagationOAuthSettings(
            github=GitHubOAuthSettings(client_id="gh-id", client_secret="gh-secret")
        ),
    )

    assert {"gh-id", "gh-secret"} <= settings.get_sensitive_fields_data()
