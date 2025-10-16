from harbor.clients.http.harbor_client import HarborClient


def init_client() -> HarborClient:
    """Initialize Harbor client from Ocean configuration."""
    return HarborClient()
