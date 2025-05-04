from typing import Any
from client import LaunchDarklyClient, ObjectKind


def extract_project_key_from_endpoint(endpoint: str, kind: str) -> str:
    """
    Extracts the project key from a LaunchDarkly API endpoint URL.

    Examples:
      Feature flag: /api/v2/flags/{project_key}/{flag_key}
      Project: /api/v2/projects/{project_key}/...
    """

    return (
        endpoint.split("/api/v2/flags/")[1].split("/")[0]
        if kind == ObjectKind.FEATURE_FLAG
        else endpoint.split("/api/v2/projects/")[1].split("/")[0]
    )


async def enrich_resource_with_project(
    endpoint: str, kind: str, client: LaunchDarklyClient
) -> dict[str, Any]:
    response = await client.send_api_request(endpoint)
    response.update({"__projectKey": extract_project_key_from_endpoint(endpoint, kind)})
    return response
