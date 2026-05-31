from loguru import logger
from port_ocean.context.ocean import ocean

from azure_devops.client.client_manager import AzureDevopsClientManager
from azure_devops.webhooks import subscription_registry


async def setup_webhooks_for_all_orgs() -> None:
    """Register webhook subscriptions for every configured organization.

    After setup, all subscription IDs are stored in the subscription registry
    so that incoming webhook events can be routed to the correct client
    by looking up payload["subscriptionId"].

    Single-org: errors propagate (same behaviour as before).
    Multi-org: a failing org is logged and skipped so the remaining orgs
    continue to be set up.
    """
    base_url = ocean.app.base_url
    webhook_secret = ocean.integration_config.get("webhook_secret")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation for ONCE listener")
        return

    if not base_url:
        logger.warning("No base url provided, skipping webhook creation")
        return

    manager = AzureDevopsClientManager.create_from_ocean_config()
    clients = manager.get_clients()
    is_multi_org = len(clients) > 1

    # Reset the registry on each startup so stale entries from a previous
    # run (e.g. after a config change that removed an org) don't linger.
    subscription_registry.clear()

    for client in clients:
        org_url = client._organization_base_url
        try:
            existing_subscriptions = await client.get_filtered_webhook_subscriptions()
            if ocean.integration_config.get("is_projects_limited"):
                sub_ids: list[str] = []
                async for projects in client.generate_projects():
                    for project in projects:
                        logger.info(
                            f"Setting up webhooks for project {project['name']} "
                            f"in org {org_url}"
                        )
                        ids = await client.create_webhook_subscriptions(
                            base_url,
                            project["id"],
                            webhook_secret,
                            existing_subscriptions=existing_subscriptions,
                        )
                        sub_ids.extend(ids)
            else:
                logger.info(f"Setting up webhooks for org {org_url}")
                sub_ids = await client.create_webhook_subscriptions(
                    base_url,
                    webhook_secret=webhook_secret,
                    existing_subscriptions=existing_subscriptions,
                )

            subscription_registry.register_many(sub_ids, client)
            logger.info(f"Registered {len(sub_ids)} subscription(s) for org {org_url}")

        except Exception as e:
            if is_multi_org:
                logger.error(
                    f"Failed to set up webhooks for org '{org_url}': {e}. "
                    "Continuing with remaining orgs."
                )
            else:
                raise

    logger.info(
        f"Subscription registry populated: {subscription_registry.size()} total entries"
    )
