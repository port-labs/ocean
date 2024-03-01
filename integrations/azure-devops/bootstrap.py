import asyncio
from loguru import logger
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.webhooks.listeners.listener import HookListener
from azure_devops.webhooks.listeners.pull_request import PullRequestHookListener
from azure_devops.webhooks.listeners.push import PushHookListener
from azure_devops.webhooks.listeners.work_item import WorkItemHookListener
from azure_devops.webhooks.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_event_observer import WebhookEventObserver

webhook_event_handler = WebhookEventObserver()


async def setup_listeners(
    app_host: str, azure_devops_client: AzureDevopsClient
) -> None:
    listeners: list[HookListener] = [
        PullRequestHookListener(azure_devops_client),
        PushHookListener(azure_devops_client),
        WorkItemHookListener(azure_devops_client),
    ]
    webhook_events: list[WebhookEvent] = list()
    for listener in listeners:
        for event in listener.webhook_events:
            event.set_consumer_url(f"{app_host}/integration/webhook")
        webhook_event_handler.on(listener.webhook_events, listener.on_hook)
        webhook_events.extend(listener.webhook_events)
    await _create_webhooks(azure_devops_client, list(webhook_events))


async def _create_webhooks(
    azure_devops_client: AzureDevopsClient, webhook_events: list[WebhookEvent]
) -> None:
    new_events = []
    existing_subscriptions: list[
        WebhookEvent
    ] = await azure_devops_client.generate_subscriptions_webhook_events()
    for event in webhook_events:
        if not event.is_event_subscribed(existing_subscriptions):
            logger.info(f"Creating new subscription for event: {str(event)}")
            new_events.append(event)
        else:
            logger.info(
                f"Event: {str(event)} already has a subscription, not creating a new one"
            )
    if new_events:
        results_with_error = await asyncio.gather(
            *(azure_devops_client.create_subscription(event) for event in new_events),
            return_exceptions=True,
        )
        errors = [
            result for result in results_with_error if isinstance(result, Exception)
        ]
        for error in errors:
            logger.error(f"Got error while creating a subscription: {str(error)}")
        logger.info(
            f"Created {len(new_events)-len(errors)} webhooks successfully with {len(errors)} failed"
        )
    else:
        logger.info("All relevant subscriptions already exist")
