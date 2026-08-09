from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean

from clients.claude_client import ClaudeClient, ClaudeDeployment

_claude_client: ClaudeClient | None = None


def create_claude_client() -> ClaudeClient:
    global _claude_client
    if _claude_client is not None:
        return _claude_client

    integration_config: dict[str, Any] = ocean.integration_config
    deployment = (
        ClaudeDeployment.ENTERPRISE
        if integration_config.get("is_claude_enterprise", True)
        else ClaudeDeployment.PLATFORM
    )
    _claude_client = ClaudeClient(
        api_host=integration_config["anthropic_api_host"],
        api_key=integration_config["anthropic_api_key"],
        anthropic_version=integration_config["anthropic_version"],
        deployment=deployment,
    )
    return _claude_client


def is_deployment_enabled(required: ClaudeDeployment, kind: str) -> bool:
    """Return whether the kind should be synced under the configured deployment.

    Platform kinds only make sense for a Claude Platform key and the per-user
    analytics kinds only for a Claude Enterprise key. When the configured
    deployment does not match, the resync is skipped (logged)
    """
    deployment = create_claude_client().deployment
    if deployment != required:
        logger.info(
            f"Skipping '{kind}' resync: integration is configured for "
            f"'{deployment.value}' deployment, but this kind requires the "
            f"'{required.value}' deployment."
        )
        return False
    return True
