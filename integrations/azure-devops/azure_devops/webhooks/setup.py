from loguru import logger

from port_ocean.context.ocean import ocean

from azure_devops.client.client_manager import AzureDevopsClientManager


async def setup_webhooks_for_all_orgs() -> None:
    """Register Azure DevOps webhook subscriptions for every configured org"""
    base_url = ocean.app.base_url
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation for ONCE listener")
        return

    if not base_url:
        logger.warning("No base url provided, skipping webhook creation")
        return

    is_projects_limited = bool(ocean.integration_config.get("is_projects_limited"))
    manager = AzureDevopsClientManager.create_from_ocean_config_no_cache()
    clients = manager.get_clients()
    webhook_secret = ocean.integration_config.get("webhook_secret")

    for org_url, client in clients:
        try:
            logger.info(f"Setting up webhooks for organization {org_url}")
            if is_projects_limited:
                async for projects in client.generate_projects():
                    for project in projects:
                        logger.info(
                            f"Setting up webhooks for project {project['name']} "
                            f"in organization {org_url}"
                        )
                        await client.create_webhook_subscriptions(
                            base_url, project["id"], webhook_secret
                        )
            else:
                await client.create_webhook_subscriptions(
                    base_url, webhook_secret=webhook_secret
                )
        except Exception as exc:
            if len(clients) == 1:
                raise
            logger.exception(
                f"Failed to set up webhooks for organization {org_url}: {exc}"
            )
