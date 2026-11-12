import pytest
import logging
from bit_bucket.bit_bucket_integration.webhook import BitbucketWebhook

@pytest.mark.asyncio
async def test_handle_event(mocker):
    """Test that the webhook handler correctly processes an event and logs it."""
    trace_id = "1098766"
    payload = {"event": "repo:push"}
    headers = {"Content-Type": "application/json"}

    webhook = BitbucketWebhook(trace_id, payload, headers)
    
    # Use spy instead of patch for better assertion tracking
    log_spy = mocker.spy(logging, "info")

    await webhook.handle_event(payload)

    # Assertions
    log_spy.assert_called_with("Webhook event received: {'event': 'repo:push'}")

@pytest.mark.asyncio
async def test_handle_event_invalid_payload(mocker):
    """Test how the webhook handles an invalid payload."""
    trace_id = "1098766"
    invalid_payload = None  # Simulate a missing payload
    headers = {"Content-Type": "application/json"}

    webhook = BitbucketWebhook(trace_id, invalid_payload, headers)
    
    log_spy = mocker.spy(logging, "error")

    await webhook.handle_event(invalid_payload)

    # Assert that an error was logged
    log_spy.assert_called_with("Invalid webhook payload received.")

@pytest.mark.asyncio
async def test_handle_event_missing_headers(mocker):
    """Test how the webhook handles missing headers."""
    trace_id = "1098766"
    payload = {"event": "repo:push"}
    missing_headers = {}  # No headers provided

    webhook = BitbucketWebhook(trace_id, payload, missing_headers)
    
    log_spy = mocker.spy(logging, "warning")

    await webhook.handle_event(payload)

    # Assert that a warning was logged
    log_spy.assert_called_with("Webhook request is missing expected headers.")