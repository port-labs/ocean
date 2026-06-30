from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from gitlab.clients.client_factory import create_gitlab_client
from gitlab.clients.gitlab_client import GitLabClient
from gitlab.webhook.webhook_factory.client_factory import GitlabWebhookFactory
from gitlab.webhook.webhook_factory.group_webhook_factory import GroupWebHook
from gitlab.webhook.webhook_factory.project_webhook_factory import ProjectWebHook
from integration import GitlabPortAppConfig


async def setup_webhooks(
    *,
    should_process_webhooks: bool,
    base_url: str | None,
    gitlab_group: str | None,
    client: GitLabClient | None = None,
    include_authenticated_user: bool | None = None,
) -> None:
    if not should_process_webhooks:
        logger.info(
            "Skipping webhook creation as it's not supported for this event listener"
        )
        return

    if not base_url:
        return

    gitlab_client = client or create_gitlab_client()

    if gitlab_group:
        logger.info(f"Creating webhooks for namespace {gitlab_group} at {base_url}")
        await GitlabWebhookFactory.create_webhooks_for_namespace(
            gitlab_client, base_url, gitlab_group
        )
        return

    logger.info(f"Creating webhooks for all owned groups at {base_url}")
    await GroupWebHook(gitlab_client, base_url).create_webhooks_for_all_groups()

    if include_authenticated_user is None:
        await ocean.integration.port_app_config_handler.get_port_app_config()
        port_config = cast(GitlabPortAppConfig, event.port_app_config)
        include_authenticated_user = port_config.include_authenticated_user

    if include_authenticated_user:
        logger.info(f"Creating webhooks for personal namespace projects at {base_url}")
        await ProjectWebHook(
            gitlab_client, base_url
        ).create_webhooks_for_personal_projects()
