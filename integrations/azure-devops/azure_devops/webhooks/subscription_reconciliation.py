import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from azure_devops.webhooks.webhook_event import WebhookSubscription

CreateSubscription = Callable[[WebhookSubscription], Awaitable[Optional[str]]]
DeleteSubscription = Callable[[WebhookSubscription], Awaitable[None]]


@dataclass(frozen=True)
class WebhookSubscriptionReconciliationPlan:
    kept_sub_ids: list[str]
    subs_to_create: list[tuple[WebhookSubscription, list[WebhookSubscription]]]
    subs_to_delete: list[WebhookSubscription]
    action_counts: Counter[str]
    skipped_project_scoped_count: int


def dedupe_subscriptions_by_id(
    subscriptions: list[WebhookSubscription],
) -> list[WebhookSubscription]:
    seen_ids: set[str] = set()
    deduped_subscriptions: list[WebhookSubscription] = []
    for subscription in subscriptions:
        if not subscription.id or subscription.id in seen_ids:
            continue
        seen_ids.add(subscription.id)
        deduped_subscriptions.append(subscription)
    return deduped_subscriptions


def plan_webhook_subscription_reconciliation(
    webhook_subscriptions: list[WebhookSubscription],
    webhook_url: str,
    auth_username: Optional[str],
    webhook_secret: Optional[str],
    project_id: Optional[str],
    existing_subscriptions: list[WebhookSubscription],
    project_scoped_only_event_types: Collection[str],
) -> WebhookSubscriptionReconciliationPlan:
    subs_to_create: list[tuple[WebhookSubscription, list[WebhookSubscription]]] = []
    subs_to_delete: list[WebhookSubscription] = []
    kept_sub_ids: list[str] = []
    action_counts: Counter[str] = Counter()
    skipped_project_scoped_count = 0

    for subscription in webhook_subscriptions:
        if not project_id and subscription.eventType in project_scoped_only_event_types:
            skipped_project_scoped_count += 1
            logger.debug(
                f"Skipping webhook subscription not supported at org level: "
                f"publisherId={subscription.publisherId}, eventType={subscription.eventType}"
            )
            continue

        desired_subscription = _build_desired_subscription(
            subscription=subscription,
            webhook_url=webhook_url,
            auth_username=auth_username,
            webhook_secret=webhook_secret,
            project_id=project_id,
        )
        matching_subscriptions = desired_subscription.get_matching_subscriptions(
            existing_subscriptions
        )
        subscription_to_keep = _select_subscription_to_keep(matching_subscriptions)

        action = "create"
        if subscription_to_keep and subscription_to_keep.id:
            kept_subscription_id = subscription_to_keep.id
            duplicate_subscriptions = [
                matching_subscription
                for matching_subscription in matching_subscriptions
                if matching_subscription.id != kept_subscription_id
            ]
            action = "keep_and_delete_duplicates" if duplicate_subscriptions else "keep"
            kept_sub_ids.append(kept_subscription_id)
            subs_to_delete.extend(duplicate_subscriptions)
        elif matching_subscriptions:
            action = "create_before_delete"
            subs_to_create.append((desired_subscription, matching_subscriptions))
        else:
            subs_to_create.append((desired_subscription, []))

        action_counts[action] += 1
        _log_webhook_reconciliation_decision(
            desired_subscription=desired_subscription,
            matching_subscriptions=matching_subscriptions,
            kept_subscription=subscription_to_keep,
            action=action,
        )

    return WebhookSubscriptionReconciliationPlan(
        kept_sub_ids=kept_sub_ids,
        subs_to_create=subs_to_create,
        subs_to_delete=subs_to_delete,
        action_counts=action_counts,
        skipped_project_scoped_count=skipped_project_scoped_count,
    )


async def create_webhook_subscription_batch(
    subs_to_create: list[tuple[WebhookSubscription, list[WebhookSubscription]]],
    create_subscription: CreateSubscription,
    max_concurrent_requests: int,
) -> tuple[list[str], list[WebhookSubscription], int]:
    created_sub_ids: list[str] = []
    stale_subscriptions_to_delete: list[WebhookSubscription] = []
    failed_create_count = 0

    if not subs_to_create:
        return created_sub_ids, stale_subscriptions_to_delete, failed_create_count

    semaphore = asyncio.BoundedSemaphore(max_concurrent_requests)

    async def create(subscription: WebhookSubscription) -> Optional[str]:
        async with semaphore:
            try:
                return await create_subscription(subscription)
            except Exception as e:
                logger.error(
                    f"Failed to create webhook subscription: "
                    f"subscription={subscription.json()}, "
                    f"errorType={type(e).__name__}, error={e}"
                )
                raise

    results = await asyncio.gather(
        *[create(sub) for sub, _ in subs_to_create],
        return_exceptions=True,
    )

    for (_, subscriptions_to_replace), result in zip(subs_to_create, results):
        if isinstance(result, Exception):
            failed_create_count += 1
            logger.error(f"Failed to create webhook: {type(result).__name__}: {result}")
        elif isinstance(result, str):
            created_sub_ids.append(result)
            stale_subscriptions_to_delete.extend(subscriptions_to_replace)

    return created_sub_ids, stale_subscriptions_to_delete, failed_create_count


async def delete_webhook_subscriptions(
    subscriptions: list[WebhookSubscription],
    delete_subscription: DeleteSubscription,
    max_deletes_per_reconciliation: int,
    max_concurrent_requests: int,
) -> None:
    subscriptions = dedupe_subscriptions_by_id(subscriptions)
    if not subscriptions:
        return

    total_subscription_count = len(subscriptions)
    subscriptions = subscriptions[:max_deletes_per_reconciliation]
    deferred_delete_count = total_subscription_count - len(subscriptions)
    if deferred_delete_count:
        logger.info(
            f"Deferring duplicate/stale webhook subscription deletes: "
            f"deferred={deferred_delete_count}, "
            f"maxPerRun={max_deletes_per_reconciliation}"
        )

    logger.info(
        f"Deleting duplicate/stale webhook subscriptions: count={len(subscriptions)}"
    )
    semaphore = asyncio.BoundedSemaphore(max_concurrent_requests)

    async def delete(subscription: WebhookSubscription) -> None:
        async with semaphore:
            await delete_subscription(subscription)

    results = await asyncio.gather(
        *[delete(subscription) for subscription in subscriptions],
        return_exceptions=True,
    )

    failed_delete_count = 0
    for subscription, result in zip(subscriptions, results):
        if isinstance(result, Exception):
            failed_delete_count += 1
            logger.error(
                f"Failed to delete duplicate webhook subscription: "
                f"subscription={subscription.json()}, "
                f"errorType={type(result).__name__}, error={result}"
            )
    logger.info(
        f"Finished deleting duplicate/stale webhook subscriptions: "
        f"requested={len(subscriptions)}, "
        f"deleted={len(subscriptions) - failed_delete_count}, "
        f"failed={failed_delete_count}, "
        f"deferred={deferred_delete_count}"
    )


def _build_desired_subscription(
    subscription: WebhookSubscription,
    webhook_url: str,
    auth_username: Optional[str],
    webhook_secret: Optional[str],
    project_id: Optional[str],
) -> WebhookSubscription:
    desired_subscription = subscription.copy(deep=True)
    desired_subscription.set_webhook_details(
        url=webhook_url,
        auth_username=auth_username,
        webhook_secret=webhook_secret,
        project_id=project_id,
    )
    return desired_subscription


def _select_subscription_to_keep(
    matching_subscriptions: list[WebhookSubscription],
) -> Optional[WebhookSubscription]:
    for subscription in matching_subscriptions:
        if (
            subscription.is_enabled()
            and subscription.id
            and subscription.has_required_payload_details()
        ):
            return subscription
    return None


def _log_webhook_reconciliation_decision(
    desired_subscription: WebhookSubscription,
    matching_subscriptions: list[WebhookSubscription],
    kept_subscription: Optional[WebhookSubscription],
    action: str,
) -> None:
    selected_subscription = kept_subscription or (
        matching_subscriptions[0] if matching_subscriptions else None
    )
    has_required_payload = (
        selected_subscription.has_required_payload_details()
        if selected_subscription
        else None
    )
    enabled_matching_count = sum(
        1 for subscription in matching_subscriptions if subscription.is_enabled()
    )
    logger.debug(
        f"Webhook subscription reconciliation decision: "
        f"desiredSubscription={desired_subscription.json()}, "
        f"selectedSubscription={selected_subscription.json() if selected_subscription else None}, "
        f"matchingSubscriptions={len(matching_subscriptions)}, "
        f"enabledMatchingSubscriptions={enabled_matching_count}, "
        f"hasRequiredPayload={has_required_payload}, action={action}"
    )
