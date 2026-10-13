from port_ocean.config.settings import (
    IdentityPropagationOAuthSettings,
    IdentityPropagationSettings,
)


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
