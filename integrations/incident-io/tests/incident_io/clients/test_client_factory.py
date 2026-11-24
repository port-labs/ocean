import pytest

from incident_io.clients.client_factory import ClientFactory


class TestClientFactory:
    def test_get_client_reuses_client(self) -> None:
        first = ClientFactory.get_client()
        second = ClientFactory.get_client()

        assert first is second
        assert first.base_url == "https://api.incident.io"

    def test_clear_drops_the_cached_client(self) -> None:
        first = ClientFactory.get_client()
        ClientFactory.clear()
        second = ClientFactory.get_client()

        assert first is not second

    def test_missing_api_key_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from port_ocean.context.ocean import ocean

        monkeypatch.setitem(ocean.integration_config, "incident_io_api_key", "  ")
        with pytest.raises(ValueError, match="incidentIoApiKey"):
            ClientFactory.get_client()
