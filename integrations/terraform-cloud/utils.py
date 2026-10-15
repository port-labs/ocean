from enum import StrEnum
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


def init_terraform_client() -> TerraformClient:
    """
    Initialize Terraform Client
    """
    config = ocean.integration_config

    terraform_client = TerraformClient(
        config["terraform_cloud_host"],
        config["terraform_cloud_token"],
    )

    return terraform_client


def should_fetch_health_assessment(workspace: dict[str, Any]) -> bool:
    if not workspace["attributes"]["assessments-enabled"]:
        return False

    relationships = workspace["relationships"]
    if "current-assessment-result" not in relationships:
        return True

    return relationships["current-assessment-result"].get("data") is not None
