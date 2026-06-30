from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from gitlab.clients.client_factory import create_gitlab_client
from gitlab.clients.gitlab_client import GitLabClient
from gitlab.webhook.webhook_factory.group_webhook_factory import GroupWebHook
from gitlab.webhook.webhook_factory.project_webhook_factory import ProjectWebHook
from integration import GitlabPortAppConfig


async def _create_personal_namespace_webhooks(
    client: GitLabClient, base_url: str
) -> None:
    """Create webhooks for all projects in the authenticated user's personal namespace."""
    logger.info("Creating webhooks for personal namespace projects")
    await ProjectWebHook(client, base_url).create_webhooks_for_personal_projects()


async def _setup_single_namespace_webhooks(
    client: GitLabClient,
    base_url: str,
    namespace: str,
    include_authenticated_user: bool,
) -> None:
    """Register webhooks for a single namespace (group or personal)."""
    logger.info(f"Creating webhooks for namespace '{namespace}'")

    if group := await client.get_group_if_exists(namespace):
        await GroupWebHook(client, base_url).create_group_webhook(group["id"])
    elif include_authenticated_user:
        await _create_personal_namespace_webhooks(client, base_url)


async def _setup_multi_group_webhooks(
    client: GitLabClient, base_url: str, include_authenticated_user: bool
) -> None:
    """Register webhooks for all owned groups, optionally including personal namespace."""
    logger.info("Creating webhooks for all owned groups")
    await GroupWebHook(client, base_url).create_webhooks_for_all_groups()

    if include_authenticated_user:
        await _create_personal_namespace_webhooks(client, base_url)


async def setup_webhooks(
    *,
    should_process_webhooks: bool,
    base_url: str | None,
    gitlab_group: str | None,
    client: GitLabClient | None = None,
) -> None:
    """Configure webhooks based on integration settings.

    Args:
        should_process_webhooks: Whether the event listener supports webhooks.
        base_url: The app's public URL for webhook callbacks.
        gitlab_group: Optional single namespace to scope webhooks to.
        client: GitLab client (created if not provided).
    """
    if not should_process_webhooks:
        logger.info(
            "Skipping webhook creation (event listener does not support webhooks)"
        )
        return

    if not base_url:
        return

    await ocean.integration.port_app_config_handler.get_port_app_config()
    port_config = cast(GitlabPortAppConfig, event.port_app_config)
    include_authenticated_user = port_config.include_authenticated_user

    gitlab_client = client or create_gitlab_client()

    if gitlab_group:
        await _setup_single_namespace_webhooks(
            gitlab_client, base_url, gitlab_group, include_authenticated_user
        )
    else:
        await _setup_multi_group_webhooks(
            gitlab_client, base_url, include_authenticated_user
        )
