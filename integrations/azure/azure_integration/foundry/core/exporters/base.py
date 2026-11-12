from __future__ import annotations

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient


class FoundryExporter:
    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client
