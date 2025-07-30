from .base import BaseFetcher
from integrations.spacelift.utils.logger import logger

QUERY = """
query {
  spaces {
    id
    name
    description
  }
}
"""

class SpacesFetcher(BaseFetcher):
    kind = "spacelift-space"

    async def fetch(self):
        logger.info("Fetching Spacelift spaces...")
        result = await self.client.query(QUERY)
        spaces = result.get("data", {}).get("spaces", [])
        logger.info(f"Fetched {len(spaces)} spaces.")

        for space in spaces:
            logger.debug(f"Yielding space: {space['id']}")
            yield {
                "identifier": space["id"],
                "title": space["name"],
                "properties": space,
            }
