from azure_devops.webhooks.subscription_reconciler import (
    dedupe_subscriptions_by_id,
    plan_webhook_subscription_reconciliation,
)
from azure_devops.webhooks.webhook_event import (
    FULL_PAYLOAD_CONSUMER_INPUTS,
    WebhookSubscription,
)


def test_plan_webhook_subscription_reconciliation_sets_details_without_mutating_source() -> (
    None
):
    source_subscription = WebhookSubscription(publisherId="tfs", eventType="git.push")

    plan = plan_webhook_subscription_reconciliation(
        webhook_subscriptions=[source_subscription],
        webhook_url="https://example.com/integration/webhook",
        auth_username="username",
        webhook_secret="secret",
        project_id="project-1",
        existing_subscriptions=[],
        project_scoped_only_event_types=set(),
    )

    desired_subscription = plan.subs_to_create[0][0]
    assert source_subscription.consumerInputs is None
    assert desired_subscription.consumerInputs == {
        "url": "https://example.com/integration/webhook",
        **FULL_PAYLOAD_CONSUMER_INPUTS,
        "basicAuthUsername": "username",
        "basicAuthPassword": "secret",
    }
    assert desired_subscription.publisherInputs == {"projectId": "project-1"}


def test_plan_webhook_subscription_reconciliation_keeps_healthy_subscription() -> None:
    desired_subscription = WebhookSubscription(publisherId="tfs", eventType="git.push")
    existing_subscription = WebhookSubscription(
        id="existing-subscription-id",
        publisherId="tfs",
        eventType="git.push",
        consumerInputs={
            "url": "https://example.com/integration/webhook",
            **FULL_PAYLOAD_CONSUMER_INPUTS,
        },
        status="enabled",
    )

    plan = plan_webhook_subscription_reconciliation(
        webhook_subscriptions=[desired_subscription],
        webhook_url="https://example.com/integration/webhook",
        auth_username=None,
        webhook_secret=None,
        project_id=None,
        existing_subscriptions=[existing_subscription],
        project_scoped_only_event_types=set(),
    )

    assert plan.kept_sub_ids == ["existing-subscription-id"]
    assert plan.subs_to_create == []
    assert plan.subs_to_delete == []


def test_plan_webhook_subscription_reconciliation_replaces_unhealthy_subscription() -> (
    None
):
    desired_subscription = WebhookSubscription(publisherId="tfs", eventType="git.push")
    existing_subscription = WebhookSubscription(
        id="existing-subscription-id",
        publisherId="tfs",
        eventType="git.push",
        consumerInputs={"url": "https://example.com/integration/webhook"},
        status="enabled",
    )

    plan = plan_webhook_subscription_reconciliation(
        webhook_subscriptions=[desired_subscription],
        webhook_url="https://example.com/integration/webhook",
        auth_username=None,
        webhook_secret=None,
        project_id=None,
        existing_subscriptions=[existing_subscription],
        project_scoped_only_event_types=set(),
    )

    assert plan.kept_sub_ids == []
    assert len(plan.subs_to_create) == 1
    assert plan.subs_to_create[0][0].consumerInputs == {
        "url": "https://example.com/integration/webhook",
        **FULL_PAYLOAD_CONSUMER_INPUTS,
    }
    assert plan.subs_to_create[0][1] == [existing_subscription]
    assert plan.subs_to_delete == []


def test_plan_webhook_subscription_reconciliation_creates_missing_subscription() -> (
    None
):
    desired_subscription = WebhookSubscription(
        publisherId="tfs",
        eventType="git.pullrequest.created",
        consumerInputs={"url": "https://example.com/integration/webhook"},
    )

    plan = plan_webhook_subscription_reconciliation(
        webhook_subscriptions=[desired_subscription],
        webhook_url="https://example.com/integration/webhook",
        auth_username=None,
        webhook_secret=None,
        project_id=None,
        existing_subscriptions=[],
        project_scoped_only_event_types=set(),
    )

    assert plan.kept_sub_ids == []
    assert len(plan.subs_to_create) == 1
    assert plan.subs_to_create[0][0].consumerInputs == {
        "url": "https://example.com/integration/webhook"
    }
    assert plan.subs_to_create[0][1] == []
    assert plan.subs_to_delete == []


def test_plan_webhook_subscription_reconciliation_skips_project_scoped_events() -> None:
    desired_subscription = WebhookSubscription(
        publisherId="tfs", eventType="git.repo.created"
    )

    plan = plan_webhook_subscription_reconciliation(
        webhook_subscriptions=[desired_subscription],
        webhook_url="https://example.com/integration/webhook",
        auth_username=None,
        webhook_secret=None,
        project_id=None,
        existing_subscriptions=[],
        project_scoped_only_event_types={"git.repo.created"},
    )

    assert plan.skipped_project_scoped_count == 1
    assert plan.subs_to_create == []


def test_dedupe_subscriptions_by_id() -> None:
    subscription = WebhookSubscription(
        id="sub-1", publisherId="tfs", eventType="git.push"
    )
    duplicate_subscription = WebhookSubscription(
        id="sub-1", publisherId="tfs", eventType="git.push"
    )
    subscription_without_id = WebhookSubscription(
        publisherId="tfs", eventType="git.push"
    )

    assert dedupe_subscriptions_by_id(
        [subscription, duplicate_subscription, subscription_without_id]
    ) == [subscription]
