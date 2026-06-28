from __future__ import annotations

from typing import Any

from port_ocean.context.ocean import ocean


def _inject_github_authorization_tokens(config: dict[str, Any]) -> None:
    resources = config.get("resources")
    if not isinstance(resources, list):
        return

    github_pat = ocean.integration_config.get("github_authorization_token")

    for resource in resources:
        if not isinstance(resource, dict):
            continue
        if resource.get("type") != "github_repository":
            continue
        if resource.get("authorization_token"):
            continue
        if not github_pat:
            raise ValueError(
                "github_authorization_token must be configured on the integration "
                "when attaching GitHub repositories without authorization_token"
            )
        resource["authorization_token"] = github_pat


async def normalize_session_config(config: dict[str, Any]) -> dict[str, Any]:
    """Prepare session create config for the Anthropic API.

    Injects GitHub authorization tokens into github_repository resources.
    MCP servers and vault credentials are declared in the workflow configuration.
    """
    working = dict(config)
    _inject_github_authorization_tokens(working)
    return working
