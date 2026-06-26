from typing import Any

ORG_MEMBERS = [
    {
        "login": "octocat",
        "id": "U_octocat",
        "databaseId": 1,
        "email": "octocat@example.com",
        "name": "Octocat",
    },
    {
        "login": "dev-user",
        "id": "U_dev",
        "databaseId": 2,
        "email": "dev@example.com",
        "name": "Dev User",
    },
]


def _page_info() -> dict[str, Any]:
    return {"hasNextPage": False, "endCursor": None}


def org_members_graphql_response(_variables: dict[str, Any]) -> dict[str, Any]:
    return {
        "data": {
            "organization": {
                "membersWithRole": {
                    "nodes": ORG_MEMBERS,
                    "pageInfo": _page_info(),
                }
            }
        }
    }
