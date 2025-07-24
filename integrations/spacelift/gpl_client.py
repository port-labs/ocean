from port_ocean.utils import http_async_client
from .auth import SpaceliftAuth
from utils.logger import logger
from utils.rate_limit import retry_with_backoff

class SpaceliftGraphQLClient:
    def __init__(self):
        self.auth = SpaceliftAuth()

    @retry_with_backoff
    async def query(self, query: str, variables: dict = None):
        headers = await self.auth.get_headers()
        payload = {
            "query": query,
            "variables": variables or {}
        }

        logger.debug("Sending GraphQL query to Spacelift...")

        response = await http_async_client.post(
            url="https://api.spacelift.io/graphql",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            logger.error(f"GraphQL errors returned: {data['errors']}")
            raise Exception("GraphQL query failed")

        logger.debug("Received response from Spacelift.")
        return data
