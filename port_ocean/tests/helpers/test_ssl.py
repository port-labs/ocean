import ssl

import pytest

from port_ocean.config.settings import (
    SslClientSettings,
    SslX509Settings,
)
from port_ocean.helpers.ssl import (
    OceanSslRole,
    resolve_verify_param,
    resolve_verify_param_for_ocean_role,
)


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        (SslClientSettings(), True),
        (SslClientSettings(verify=False), False),
    ],
)
def test_resolve_verify_param_default_and_disabled(
    settings: SslClientSettings, expected: bool
) -> None:
    assert resolve_verify_param(settings) is expected


def test_resolve_verify_param_x509_non_strict_returns_ssl_context() -> None:
    settings = SslClientSettings(x509=SslX509Settings(strict=False))
    result = resolve_verify_param(settings)

    assert isinstance(result, ssl.SSLContext)
    assert result.verify_mode == ssl.CERT_REQUIRED
    assert result.check_hostname is True
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        assert not result.verify_flags & ssl.VERIFY_X509_STRICT


@pytest.mark.parametrize("role", ["port", "third_party"])
def test_resolve_verify_param_for_ocean_role_without_context_returns_true(
    role: OceanSslRole,
) -> None:
    assert resolve_verify_param_for_ocean_role(role) is True


def test_integration_configuration_reads_structured_ssl_env_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from port_ocean.config.settings import IntegrationConfiguration

    monkeypatch.setenv("OCEAN__SSL__PORT__X509__STRICT", "false")
    monkeypatch.setenv("OCEAN__SSL__THIRD_PARTY__VERIFY", "false")
    monkeypatch.setenv("OCEAN__PORT__CLIENT_ID", "test-client-id")
    monkeypatch.setenv("OCEAN__PORT__CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OCEAN__INTEGRATION__TYPE", "test")
    monkeypatch.setenv("OCEAN__INTEGRATION__IDENTIFIER", "test-id")

    config = IntegrationConfiguration()

    assert config.ssl.port.x509.strict is False
    assert config.ssl.third_party.verify is False
