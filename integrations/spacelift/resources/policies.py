from .base import BaseFetcher

POLICIES_QUERY = """
query {
  policies {
    id
    name
    policyType
    description
    context
    labels
    createdAt
    updatedAt
    stack {
      id
      name
    }
  }
}
"""

class PoliciesFetcher(BaseFetcher):
    kind = "spacelift-policy"

    async def fetch(self):
        result = await self.client.query(POLICIES_QUERY)
        policies = result.get("data", {}).get("policies", [])

        for policy in policies:
            yield {
                "identifier": policy["id"],
                "title": policy["name"],
                "properties": {
                    "type": policy.get("policyType"),
                    "description": policy.get("description"),
                    "context": policy.get("context"),
                    "labels": policy.get("labels"),
                    "created_at": policy.get("createdAt"),
                    "updated_at": policy.get("updatedAt"),
                    "stack_id": policy.get("stack", {}).get("id"),
                    "stack_name": policy.get("stack", {}).get("name"),
                },
            }
