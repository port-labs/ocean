import asyncio
import httpx
from .utils.auth import get_jwt_token
from .config import SpaceliftConfig
from .constants import GRAPHQL_URL_TEMPLATE

class SpaceliftClient:
    def __init__(self, config: SpaceliftConfig):
        self.cfg = config
        self.base_url = GRAPHQL_URL_TEMPLATE.format(account=self.cfg.spacelift_account)
        self.client = httpx.AsyncClient()
        self.jwt = None

    async def authenticate(self):
        self.jwt = get_jwt_token(self.cfg)

    async def query(self, query: str, variables: dict = None):
        if not self.jwt:
            await self.authenticate()

        headers = {"Authorization": f"Bearer {self.jwt}"}
        resp = await self.client.post(self.base_url, json={"query": query, "variables": variables or {}}, headers=headers)
        resp.raise_for_status()  # Optional: raises an exception for 4xx/5xx responses
        return resp.json().get("data")