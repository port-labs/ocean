from .base import BaseFetcher

USERS_QUERY = """
query {
  users {
    id
    email
    name
    avatar
    isAdmin
    createdAt
    externalId
  }
}
"""

class UsersFetcher(BaseFetcher):
    kind = "spacelift-user"

    async def fetch(self):
        result = await self.client.query(USERS_QUERY)
        users = result.get("data", {}).get("users", [])

        for user in users:
            yield {
                "identifier": user["id"],
                "title": user.get("name") or user["email"],
                "properties": {
                    "email": user["email"],
                    "name": user.get("name"),
                    "avatar": user.get("avatar"),
                    "is_admin": user.get("isAdmin"),
                    "created_at": user.get("createdAt"),
                    "external_id": user.get("externalId"),
                },
            }
