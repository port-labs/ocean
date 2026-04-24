from enum import StrEnum
from typing import Any


class ObjectKind(StrEnum):
    SPACE = "space"
    PROJECT = "project"
    DEPLOYMENT = "deployment"
    RELEASE = "release"
    MACHINE = "machine"


def build_resource_url(resource: dict[str, Any], kind: str, server_url: str) -> str:
    resource_id = resource["Id"]
    space_id = resource.get("SpaceId", "")
    base = f"{server_url}/app#/{space_id}"

    paths: dict[str, str] = {
        ObjectKind.SPACE: f"{server_url}/app#/{resource_id}",
        ObjectKind.PROJECT: f"{base}/projects/{resource_id}",
        ObjectKind.RELEASE: f"{base}/releases/{resource_id}",
        ObjectKind.DEPLOYMENT: f"{base}/deployments/{resource_id}",
        ObjectKind.MACHINE: f"{base}/infrastructure/machines/{resource_id}/settings",
    }
    return paths.get(kind, "")
