import asyncio
from loguru import logger
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.webhooks.listeners.listener import HookListener
from azure_devops.webhooks.listeners.pull_request import PullRequestHookListener
from azure_devops.webhooks.listeners.push import PushHookListener
from azure_devops.webhooks.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_event_observer import WebhookEventObserver

webhook_event_handler = WebhookEventObserver()


async def setup_listeners(
    app_host: str, azure_devops_client: AzureDevopsClient, project_id: str | None = None
) -> None:
    listeners: list[HookListener] = [
        PullRequestHookListener(azure_devops_client),
        PushHookListener(azure_devops_client),
    ]
    webhook_events: list[WebhookEvent] = list()
    for listener in listeners:
        for event in listener.webhook_events:
            event.set_webhook_details(f"{app_host}/integration/webhook", project_id)
        webhook_event_handler.on(listener.webhook_events, listener.on_hook)
        webhook_events.extend(listener.webhook_events)
    await _upsert_webhooks(azure_devops_client, webhook_events)


async def _upsert_webhooks(
    azure_devops_client: AzureDevopsClient, webhook_events: list[WebhookEvent]
) -> None:
    events_to_create = []
    events_to_delete = []
    existing_subscriptions: list[WebhookEvent] = (
        await azure_devops_client.generate_subscriptions_webhook_events()
    )
    for event in webhook_events:
        webhook_subscription = event.get_event_by_subscription(existing_subscriptions)
        if webhook_subscription is not None and not webhook_subscription.is_enabled():
            logger.info("Subscription is disabled, deleting it and creating a new one")
            events_to_create.append(event)
            events_to_delete.append(webhook_subscription)
        elif event.get_event_by_subscription(existing_subscriptions) is None:
            events_to_create.append(event)
        else:
            logger.info(
                f"Event: {str(event)} already has a subscription, not creating a new one"
            )
    if events_to_delete:
        logger.info(f"Deleting {len(events_to_delete)} subscriptions")
        await asyncio.gather(
            *(
                azure_devops_client.delete_subscription(subscription)
                for subscription in events_to_delete
            )
        )
        logger.info(f"Deleted {len(events_to_delete)} subscriptions")

    if events_to_create:
        logger.info(f"Creating new subscription for event: {str(event)}")
        results_with_error = await asyncio.gather(
            *(
                azure_devops_client.create_subscription(event)
                for event in events_to_create
            ),
            return_exceptions=True,
        )
        errors = [
            result for result in results_with_error if isinstance(result, Exception)
        ]
        for error in errors:
            logger.error(f"Got error while creating a subscription: {str(error)}")
        logger.info(
            f"Created {len(events_to_create)-len(errors)} webhooks successfully with {len(errors)} failed"
        )

    else:
        logger.info("All relevant subscriptions already exist")
