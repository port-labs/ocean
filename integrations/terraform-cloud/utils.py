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


_client: TerraformClient | None = None


def init_terraform_client() -> TerraformClient:
    """
    Initialize Terraform Client

    Cached because the client owns an HTTP connection pool, and live events build one
    per delivered event. One client per process is also one rate limiter per process,
    so every caller draws on the same view of the API's budget.

    No fork guard: the only fork is the JQ entity processor's pool
    (port_ocean/core/handlers/entity_processor/jq_entity_processor.py:421), whose child
    runs mapping alone and never asks for a client. An entity-processor hook that
    fetched during mapping would need the os.register_at_fork reset in
    github/github/clients/client_factory.py:32.
    """
    global _client

    if _client is None:
        config = ocean.integration_config

        _client = TerraformClient(
            config["terraform_cloud_host"],
            config["terraform_cloud_token"],
        )

    return _client


def should_fetch_health_assessment(workspace: dict[str, Any]) -> bool:
    if not workspace["attributes"]["assessments-enabled"]:
        return False

    relationships = workspace["relationships"]
    if "current-assessment-result" not in relationships:
        return True

    return relationships["current-assessment-result"].get("data") is not None
