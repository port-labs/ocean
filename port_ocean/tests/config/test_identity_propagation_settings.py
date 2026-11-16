import pytest
from pydantic import ValidationError

from port_ocean.config.settings import (
    IdentityPropagationOAuthSettings,
    IdentityPropagationSettings,
    IntegrationConfiguration,
)


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCEAN__PORT__CLIENT_ID", "test-client-id")
    monkeypatch.setenv("OCEAN__PORT__CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OCEAN__INTEGRATION__TYPE", "test")
    monkeypatch.setenv("OCEAN__INTEGRATION__IDENTIFIER", "test-id")


def test_identity_propagation_is_disabled_by_default() -> None:
    settings = IdentityPropagationSettings()

    assert settings.enabled is False
    assert settings.vault.secret_prefix == "port/tokens"
    assert settings.oauth.state_signing_secret is None


def test_state_signing_secret_can_be_set() -> None:
    settings = IdentityPropagationOAuthSettings(state_signing_secret="my-secret")

    assert settings.state_signing_secret == "my-secret"


def test_state_signing_secret_is_marked_sensitive() -> None:
    settings = IdentityPropagationSettings(
        enabled=True,
        oauth=IdentityPropagationOAuthSettings(state_signing_secret="s3cret"),
    )

    assert "s3cret" in settings.get_sensitive_fields_data()


def test_port_vault_rejected_on_on_prem_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("OCEAN__RUNTIME", "OnPrem")
    monkeypatch.setenv("OCEAN__IDENTITY_PROPAGATION__VAULT__TYPE", "port")

    with pytest.raises(ValidationError, match="only supported on SaaS"):
        IntegrationConfiguration()


def test_port_vault_allowed_on_saas_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setattr(
        "port_ocean.config.settings.get_spec_file",
        lambda *args, **kwargs: {"saas": {"enabled": True}},
    )
    monkeypatch.setenv("OCEAN__RUNTIME", "Saas")
    monkeypatch.setenv("OCEAN__IDENTITY_PROPAGATION__VAULT__TYPE", "port")

    config = IntegrationConfiguration()

    assert config.identity_propagation.vault.type.value == "port"


def test_aws_vault_still_allowed_on_on_prem(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("OCEAN__RUNTIME", "OnPrem")
    monkeypatch.setenv(
        "OCEAN__IDENTITY_PROPAGATION__VAULT__TYPE", "aws_secrets_manager"
    )

    config = IntegrationConfiguration()

    assert config.identity_propagation.vault.type.value == "aws_secrets_manager"
