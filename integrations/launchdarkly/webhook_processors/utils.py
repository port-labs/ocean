from typing import Any
from client import LaunchDarklyClient, ObjectKind


def extract_project_key_from_endpoint(endpoint: str, kind: str) -> str:
    """
    Extracts the project key from a LaunchDarkly API endpoint URL.

    Examples:
      Feature flag: /api/v2/flags/{project_key}/{flag_key}
      Project: /api/v2/projects/{project_key}/...
      Segment: /api/v2/segments/{project_key}/{environment_key}/{segment_key}
    """

    if kind == ObjectKind.FEATURE_FLAG:
        return endpoint.split("/api/v2/flags/")[1].split("/")[0]
    elif kind == ObjectKind.SEGMENT:
        return endpoint.split("/api/v2/segments/")[1].split("/")[0]
    else:
        return endpoint.split("/api/v2/projects/")[1].split("/")[0]


async def enrich_resource_with_project(
    endpoint: str, kind: str, client: LaunchDarklyClient
) -> dict[str, Any]:
    response = await client.send_api_request(endpoint)
    response.update({"__projectKey": extract_project_key_from_endpoint(endpoint, kind)})
    return response
