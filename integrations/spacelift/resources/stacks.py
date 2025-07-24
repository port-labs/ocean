from .base import BaseFetcher
from integrations.spacelift.utils.logger import logger

STACKS_QUERY = """
query {
  stacks {
    id
    name
    description
    repository
    branch
    isDetached
    administrative
    terraformVersion
    createdAt
    labels
  }
}
"""

class StacksFetcher(BaseFetcher):
    kind = "spacelift-stack"

    async def fetch(self):
        logger.info("Fetching Spacelift stacks...")
        result = await self.client.query(STACKS_QUERY)
        stacks = result.get("data", {}).get("stacks", [])
        logger.info(f"Fetched {len(stacks)} stacks.")

        for stack in stacks:
            logger.debug(f"Yielding stack: {stack['id']}")
            yield {
                "identifier": stack["id"],
                "title": stack["name"],
                "properties": {
                    "description": stack.get("description"),
                    "repository": stack.get("repository"),
                    "branch": stack.get("branch"),
                    "is_detached": stack.get("isDetached"),
                    "administrative": stack.get("administrative"),
                    "terraform_version": stack.get("terraformVersion"),
                    "created_at": stack.get("createdAt"),
                    "labels": stack.get("labels"),
                },
            }
