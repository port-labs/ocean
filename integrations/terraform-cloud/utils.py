from enum import StrEnum

from client import TerraformClient
from port_ocean.context.ocean import ocean


class ObjectKind(StrEnum):
    WORKSPACE = "workspace"
    RUN = "run"
    STATE_VERSION = "state-version"
    STATE_FILE = "state-file"
    PROJECT = "project"
    ORGANIZATION = "organization"


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
