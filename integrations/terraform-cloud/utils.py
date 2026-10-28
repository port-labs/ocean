from enum import StrEnum
from functools import lru_cache
from typing import Any

from client import TerraformClient
from port_ocean.context.ocean import ocean


class ObjectKind(StrEnum):
    WORKSPACE = "workspace"
    RUN = "run"
    STATE_VERSION = "state-version"
    STATE_FILE = "state-file"
    PROJECT = "project"
    ORGANIZATION = "organization"
    HEALTH_ASSESSMENT = "health-assessment"


@lru_cache(maxsize=1)
def init_terraform_client() -> TerraformClient:
    """One client per process: one connection pool, one rate limiter budget."""
    return TerraformClient(
        ocean.integration_config["terraform_cloud_host"],
        ocean.integration_config["terraform_cloud_token"],
    )


def should_fetch_health_assessment(workspace: dict[str, Any]) -> bool:
    if not workspace["attributes"]["assessments-enabled"]:
        return False

    relationships = workspace["relationships"]
    if "current-assessment-result" not in relationships:
        return True

    return relationships["current-assessment-result"].get("data") is not None
