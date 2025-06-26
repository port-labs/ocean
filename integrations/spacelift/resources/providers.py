from .base import BaseFetcher

PROVIDERS_QUERY = """query { providers { id name type createdAt } }"""

class ProvidersFetcher(BaseFetcher):
    kind = "spacelift-provider"

    async def fetch(self):
        result = await self.client.query(PROVIDERS_QUERY)
        for p in result["data"]["providers"]:
            yield {
                "identifier": p["id"],
                "title": p["name"],
                "properties": p,
            }
