from typing import Any

from mocks.payloads import ORG_LOGIN, REPO_NAMES

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


def team_with_members_graphql_response(variables: dict[str, Any]) -> dict[str, Any]:
    slug = variables.get("slug", "team-alpha")
    return {
        "data": {
            "organization": {
                "team": {
                    "id": "T_ALPHA",
                    "slug": slug,
                    "databaseId": 1,
                    "name": "Team Alpha",
                    "description": "Team Alpha",
                    "privacy": "VISIBLE",
                    "notificationSetting": "NOTIFICATIONS_ENABLED",
                    "url": f"https://github.com/orgs/{ORG_LOGIN}/teams/{slug}",
                    "members": {
                        "nodes": [
                            {
                                "id": "M1",
                                "login": "team-member",
                                "name": "Team Member",
                                "email": "team-member@example.com",
                                "isSiteAdmin": False,
                            }
                        ],
                        "pageInfo": _page_info(),
                    },
                }
            }
        }
    }


def pull_requests_graphql_response(variables: dict[str, Any]) -> dict[str, Any]:
    organization = variables["organization"]
    repo = variables["repo"]
    repo_index = REPO_NAMES.index(repo) if repo in REPO_NAMES else 0
    pr_number = 1
    return {
        "data": {
            "repository": {
                "pullRequests": {
                    "nodes": [
                        {
                            "url": f"https://github.com/{organization}/{repo}/pull/{pr_number}",
                            "id": f"PR_{repo}_{pr_number}",
                            "fullDatabaseId": str(10001 + repo_index),
                            "number": pr_number,
                            "title": f"Test PR for {repo}",
                            "state": "OPEN",
                            "commits": {"totalCount": 1},
                        }
                    ],
                    "pageInfo": _page_info(),
                }
            }
        }
    }
