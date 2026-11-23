from coralogix.clients.client_factory import ClientFactory


class TestClientFactory:
    def test_get_client_resolves_region_and_reuses_client(self) -> None:
        first = ClientFactory.get_client()
        second = ClientFactory.get_client()

        assert first is second
        assert first.base_url == "https://api.eu2.coralogix.com"

    def test_clear_drops_the_cached_client(self) -> None:
        first = ClientFactory.get_client()
        ClientFactory.clear()
        second = ClientFactory.get_client()

        assert first is not second
