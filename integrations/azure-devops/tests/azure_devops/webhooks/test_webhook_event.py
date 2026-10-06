from azure_devops.webhooks.webhook_event import (
    FULL_PAYLOAD_CONSUMER_INPUTS,
    WebhookSubscription,
)


def test_set_webhook_details_requests_full_payload_for_push() -> None:
    subscription = WebhookSubscription(publisherId="tfs", eventType="git.push")

    subscription.set_webhook_details("https://example.com/webhook")

    assert subscription.consumerInputs == {
        "url": "https://example.com/webhook",
        **FULL_PAYLOAD_CONSUMER_INPUTS,
    }


def test_set_webhook_details_keeps_default_payload_for_other_events() -> None:
    subscription = WebhookSubscription(
        publisherId="tfs", eventType="git.pullrequest.created"
    )

    subscription.set_webhook_details("https://example.com/webhook")

    assert subscription.consumerInputs == {"url": "https://example.com/webhook"}


def test_set_webhook_details_clears_project_scope_for_org_level_subscription() -> None:
    subscription = WebhookSubscription(
        publisherId="tfs",
        eventType="git.push",
        publisherInputs={"projectId": "previous-project"},
    )

    subscription.set_webhook_details("https://example.com/webhook")

    assert subscription.publisherInputs is None


def test_has_required_payload_details_rejects_minimal_push_subscription() -> None:
    subscription = WebhookSubscription(
        publisherId="tfs",
        eventType="git.push",
        consumerInputs={"url": "https://example.com/webhook"},
    )

    assert not subscription.has_required_payload_details()


def test_has_required_payload_details_accepts_full_push_subscription() -> None:
    subscription = WebhookSubscription(
        publisherId="tfs",
        eventType="git.push",
        consumerInputs={
            "url": "https://example.com/webhook",
            **FULL_PAYLOAD_CONSUMER_INPUTS,
        },
    )

    assert subscription.has_required_payload_details()


def test_get_event_by_subscription_matches_org_level_subscription_with_tfs_subscription_id() -> (
    None
):
    subscription = WebhookSubscription(
        publisherId="tfs",
        eventType="git.push",
        consumerInputs={
            "url": "https://example.com/webhook",
            **FULL_PAYLOAD_CONSUMER_INPUTS,
        },
    )
    existing_subscription = WebhookSubscription(
        id="existing-subscription-id",
        publisherId="tfs",
        eventType="git.push",
        consumerInputs={
            "url": "https://example.com/webhook",
            **FULL_PAYLOAD_CONSUMER_INPUTS,
        },
        publisherInputs={"tfsSubscriptionId": "ado-generated-subscription-id"},
    )

    assert (
        subscription.get_event_by_subscription([existing_subscription])
        == existing_subscription
    )


def test_get_event_by_subscription_matches_same_project_subscription() -> None:
    subscription = WebhookSubscription(
        publisherId="tfs",
        eventType="git.push",
        consumerInputs={
            "url": "https://example.com/webhook",
            **FULL_PAYLOAD_CONSUMER_INPUTS,
        },
        publisherInputs={"projectId": "project-1"},
    )
    existing_subscription = WebhookSubscription(
        id="existing-subscription-id",
        publisherId="tfs",
        eventType="git.push",
        consumerInputs={
            "url": "https://example.com/webhook",
            **FULL_PAYLOAD_CONSUMER_INPUTS,
        },
        publisherInputs={
            "projectId": "project-1",
            "tfsSubscriptionId": "ado-generated-subscription-id",
        },
    )

    assert (
        subscription.get_event_by_subscription([existing_subscription])
        == existing_subscription
    )


def test_get_event_by_subscription_does_not_match_different_project_subscription() -> (
    None
):
    subscription = WebhookSubscription(
        publisherId="tfs",
        eventType="git.push",
        consumerInputs={
            "url": "https://example.com/webhook",
            **FULL_PAYLOAD_CONSUMER_INPUTS,
        },
        publisherInputs={"projectId": "project-1"},
    )
    existing_subscription = WebhookSubscription(
        id="existing-subscription-id",
        publisherId="tfs",
        eventType="git.push",
        consumerInputs={
            "url": "https://example.com/webhook",
            **FULL_PAYLOAD_CONSUMER_INPUTS,
        },
        publisherInputs={
            "projectId": "project-2",
            "tfsSubscriptionId": "ado-generated-subscription-id",
        },
    )

    assert subscription.get_event_by_subscription([existing_subscription]) is None
