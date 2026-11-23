from confluence.clients.client_factory import ClientFactory


class TestClientFactory:
    def test_get_client_returns_a_singleton(self) -> None:
        first = ClientFactory.get_client()
        second = ClientFactory.get_client()

        assert first is second
        assert first.site_url == "https://example.atlassian.net"

    def test_clear_drops_the_cached_client(self) -> None:
        first = ClientFactory.get_client()
        ClientFactory.clear()
        second = ClientFactory.get_client()

        assert first is not second
