import asyncio
from loguru import logger
from azure_devops.client import AzureDevopsHTTPClient
from azure_devops.webhooks.listeners.listener import HookListener
from azure_devops.webhooks.listeners.pull_request import PullRequestHookListener
from azure_devops.webhooks.listeners.push import PushHookListener
from azure_devops.webhooks.listeners.work_item import WorkItemHookListener
from azure_devops.webhooks.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_event_observer import WebhookEventObserver

webhook_event_handler = WebhookEventObserver()


async def setup_listeners(
    app_host: str, azure_devops_client: AzureDevopsHTTPClient
) -> None:
    listeners: list[HookListener] = [
        PullRequestHookListener(azure_devops_client),
        PushHookListener(azure_devops_client),
        WorkItemHookListener(azure_devops_client),
    ]
    webhook_events = set()
    for listener in listeners:
        for event in listener.webhook_events:
            event.set_consumer_url(f"{app_host}/integration/webhook")
        webhook_event_handler.on(listener.webhook_events, listener.on_hook)
        webhook_events.update(listener.webhook_events)
    await _create_webhooks(azure_devops_client, list(webhook_events))


async def _create_webhooks(
    azure_devops_client: AzureDevopsHTTPClient, webhook_events: list[WebhookEvent]
) -> None:
    logger.info(f"Creating webhooks: {webhook_events}")
    new_events = []
    existing_subscriptions: list[
        WebhookEvent
    ] = await azure_devops_client.generate_subscriptions_webhook_events()
    try:
        for event in webhook_events:
            if event in existing_subscriptions:
                logger.debug(f"Creating new subscription for event: {str(event)}")
                new_events.append(event)
        await asyncio.gather(
            *(azure_devops_client.create_subscription(event) for event in new_events)
        )
        if new_events:
            logger.info(f"Created {len(new_events)} webhooks successfully")
        else:
            logger.info(
                "All relevant subscriptions already exist, not creating any new ones.."
            )
    except Exception as e:
        logger.error(f"Failed to create a subscription: {str(e)}")
    return
