from typing import Any, AsyncGenerator

from clients.armorcode_client import ArmorcodeClient


class ProductExporter:
    def __init__(self, client: ArmorcodeClient) -> None:
        self.client = client

    def get_paginated_resources(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        return self.client.get_products()
