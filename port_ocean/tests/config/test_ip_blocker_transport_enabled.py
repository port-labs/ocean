import pytest

from port_ocean.config.settings import IntegrationConfiguration


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCEAN__PORT__CLIENT_ID", "test-client-id")
    monkeypatch.setenv("OCEAN__PORT__CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OCEAN__INTEGRATION__TYPE", "test")
    monkeypatch.setenv("OCEAN__INTEGRATION__IDENTIFIER", "test-id")


def _mock_saas_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "port_ocean.config.settings.get_spec_file",
        lambda *args, **kwargs: {"saas": {"enabled": True}},
    )


class TestDisableIpOutboundBlocker:
    def test_defaults_to_false_on_saas_runtime(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_required_env(monkeypatch)
        _mock_saas_spec(monkeypatch)
        monkeypatch.setenv("OCEAN__RUNTIME", "Saas")

        config = IntegrationConfiguration()

        assert config.disable_ip_outbound_blocker is False

    def test_defaults_to_true_on_on_prem_runtime(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_required_env(monkeypatch)
        monkeypatch.setenv("OCEAN__RUNTIME", "OnPrem")

        config = IntegrationConfiguration()

        assert config.disable_ip_outbound_blocker is True

    def test_explicit_env_disables_on_saas(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_required_env(monkeypatch)
        _mock_saas_spec(monkeypatch)
        monkeypatch.setenv("OCEAN__RUNTIME", "Saas")
        monkeypatch.setenv("OCEAN__DISABLE_IP_OUTBOUND_BLOCKER", "true")

        config = IntegrationConfiguration()

        assert config.disable_ip_outbound_blocker is True

    def test_explicit_env_enables_on_on_prem(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_required_env(monkeypatch)
        monkeypatch.setenv("OCEAN__RUNTIME", "OnPrem")
        monkeypatch.setenv("OCEAN__DISABLE_IP_OUTBOUND_BLOCKER", "false")

        config = IntegrationConfiguration()

        assert config.disable_ip_outbound_blocker is False
