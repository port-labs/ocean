from httpx import BasicAuth, Timeout
from loguru import logger
from port_ocean.utils import http_async_client
from typing import Any


class HiBobClient:
    def __init__(self, api_url: str, username: str, password: str):
        self.api_url = api_url
        self.username = username
        self.password = password
        logger.info(f"Initializing Hibob client with API {api_url} and API service username {username}")
        self.client = http_async_client
        self.client.auth = BasicAuth(username, password)
        self.client.timeout = Timeout(30)

    async def get_profiles(self) -> list[dict[str, Any]]:
        logger.info("Getting profiles from HiBob")
        profiles_response = await self.client.get(f"{self.api_url}/v1/profiles")
        profiles_response.raise_for_status()
        return profiles_response.json()["employees"]

    async def get_all_lists(self) -> dict[str, Any]:
        logger.info("Getting all company lists from HiBob")
        lists_responses = await self.client.get(
            f"{self.api_url}/v1/company/named-lists"
        )
        lists_responses.raise_for_status()
        return lists_responses.json()
