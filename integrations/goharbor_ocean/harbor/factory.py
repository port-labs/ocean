"""
Factory module for managing client lifecycle
"""

from typing import Optional
from loguru import logger

from port_ocean.context.ocean import ocean
from harbor.client import HarborClient


class HarborClientFactory:
    _instance: Optional[HarborClient] = None

    @classmethod
    def get_client(cls) -> HarborClient:
        if cls._instance is None:
            cls._instance = cls._create_client()
        return cls._instance

    @classmethod
    def _create_client(cls) -> HarborClient:
        config = ocean.integration_config

        harbor_url = str(config.get("harbor_url", ""))
        harbor_username = config.get("harbor_username", "")
        harbor_password = config.get("harbor_password", "")
        verify_ssl = config.get("verify_ssl", True)

        if not all([harbor_url, harbor_username, harbor_password]):
            raise ValueError("Missing required Harbor configuration")

        logger.info(f"harbor_ocean::factory::Initializing Harbor client for {harbor_url}")
        return HarborClient(
            base_url=harbor_url,
            username=harbor_username,
            password=harbor_password,
            verify_ssl=verify_ssl,
        )
