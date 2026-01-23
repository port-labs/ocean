"""Tests for Harbor webhook handler."""

import hmac
import hashlib
import pytest
from unittest.mock import AsyncMock, patch
from harbor.webhooks.webhook_handler import HarborWebhookHandler


# Signature Verification Tests
def test_webhook_signature_verification():
    """Test webhook signature verification with valid and invalid signatures."""
    webhook_handler = HarborWebhookHandler(webhook_secret="test-secret")

    payload = b'{"type": "PUSH_ARTIFACT", "event_data": {}}'
    computed_signature = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()

    assert webhook_handler.verify_signature(computed_signature, payload) is True
    assert webhook_handler.verify_signature("invalid-signature", payload) is False


def test_webhook_signature_verification_no_secret():
    """Test webhook allows all requests when no secret is configured."""
    webhook_handler = HarborWebhookHandler()

    payload = b'{"type": "PUSH_ARTIFACT"}'
    any_signature = "any-signature"

    assert webhook_handler.verify_signature(any_signature, payload) is True


@pytest.mark.asyncio
async def test_webhook_handler_with_secret():
    """Test webhook handler signature verification with secret."""
    secret = "my-webhook-secret"
    webhook_handler = HarborWebhookHandler(webhook_secret=secret)

    payload = b'{"type": "PUSH_ARTIFACT"}'
    valid_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert webhook_handler.verify_signature(valid_signature, payload) is True
    assert webhook_handler.verify_signature("wrong-signature", payload) is False


@pytest.mark.asyncio
async def test_webhook_handler_without_secret():
    """Test webhook handler allows all requests when no secret is configured."""
    webhook_handler = HarborWebhookHandler(webhook_secret=None)

    assert webhook_handler.verify_signature("any-signature", b"any-payload") is True
    assert webhook_handler.verify_signature("", b"") is True


# Event Routing Tests
@pytest.mark.asyncio
async def test_webhook_handler_event_routing():
    """Test that webhook handler correctly routes different event types."""
    webhook_handler = HarborWebhookHandler()

    with patch.object(webhook_handler, "_handle_push_artifact", new_callable=AsyncMock) as mock_push:
        await webhook_handler.handle_webhook_event("PUSH_ARTIFACT", {"test": "data"})
        mock_push.assert_called_once_with({"test": "data"})

    with patch.object(webhook_handler, "_handle_delete_artifact", new_callable=AsyncMock) as mock_delete:
        await webhook_handler.handle_webhook_event("DELETE_ARTIFACT", {"test": "data"})
        mock_delete.assert_called_once_with({"test": "data"})

    with patch.object(webhook_handler, "_handle_scanning_completed", new_callable=AsyncMock) as mock_scan:
        await webhook_handler.handle_webhook_event("SCANNING_COMPLETED", {"test": "data"})
        mock_scan.assert_called_once_with({"test": "data"})


@pytest.mark.asyncio
async def test_webhook_handle_scanning_failed_event_routing():
    """Test that SCANNING_FAILED event is routed correctly."""
    webhook_handler = HarborWebhookHandler()

    with patch.object(webhook_handler, "_handle_scanning_failed", new_callable=AsyncMock) as mock_failed:
        await webhook_handler.handle_webhook_event("SCANNING_FAILED", {"test": "data"})
        mock_failed.assert_called_once_with({"test": "data"})


@pytest.mark.asyncio
async def test_webhook_handle_unknown_event():
    """Test handling of unknown webhook event types."""
    webhook_handler = HarborWebhookHandler()

    # Should not raise an error for unknown events
    await webhook_handler.handle_webhook_event("UNKNOWN_EVENT", {"test": "data"})


# Push Artifact Handler Tests
@pytest.mark.asyncio
async def test_webhook_handle_push_artifact():
    """Test handling of PUSH_ARTIFACT webhook event."""
    webhook_handler = HarborWebhookHandler()

    event_data = {"repository": {"namespace": "library", "name": "nginx"}}

    with patch.object(webhook_handler, "_get_harbor_client") as mock_get_client:
        mock_client = AsyncMock()

        async def mock_get_artifacts(*args, **kwargs):
            yield {"digest": "sha256:abc123", "tags": [{"name": "latest"}]}

        mock_client.get_artifacts = mock_get_artifacts
        mock_get_client.return_value = mock_client

        with patch.object(webhook_handler, "_upsert_artifact") as mock_upsert:
            await webhook_handler._handle_push_artifact(event_data)
            assert mock_upsert.called


@pytest.mark.asyncio
async def test_webhook_handle_push_artifact_missing_data():
    """Test handling of PUSH_ARTIFACT with missing repository data."""
    webhook_handler = HarborWebhookHandler()

    # Missing namespace
    event_data = {"repository": {"name": "nginx"}}
    await webhook_handler._handle_push_artifact(event_data)  # Should not raise

    # Missing name
    event_data = {"repository": {"namespace": "library"}}
    await webhook_handler._handle_push_artifact(event_data)  # Should not raise

    # Empty repository
    event_data = {"repository": {}}
    await webhook_handler._handle_push_artifact(event_data)  # Should not raise


# Delete Artifact Handler Tests
@pytest.mark.asyncio
async def test_webhook_handle_delete_artifact():
    """Test handling of DELETE_ARTIFACT webhook event."""
    webhook_handler = HarborWebhookHandler()

    event_data = {
        "resources": [{"digest": "sha256:abc123456789", "resource_url": "harbor.example.com/library/nginx:latest"}]
    }

    with patch("harbor.webhooks.webhook_handler.ocean") as mock_ocean:
        mock_ocean.unregister_raw = AsyncMock()

        await webhook_handler._handle_delete_artifact(event_data)

        assert mock_ocean.unregister_raw.called
        call_args = mock_ocean.unregister_raw.call_args
        assert call_args.args[0] == "artifact"
        assert "identifier" in call_args.args[1][0]


# Scanning Completed Handler Tests
@pytest.mark.asyncio
async def test_webhook_handle_scanning_completed():
    """Test handling of SCANNING_COMPLETED webhook event."""
    webhook_handler = HarborWebhookHandler()

    event_data = {"repository": {"namespace": "library", "name": "nginx"}}

    with patch.object(webhook_handler, "_get_harbor_client") as mock_get_client:
        mock_client = AsyncMock()

        async def mock_get_artifacts(*args, **kwargs):
            yield {
                "digest": "sha256:abc123",
                "tags": [{"name": "latest"}],
                "scan_overview": {"test": {"scan_status": "Success", "severity": "High"}},
            }

        mock_client.get_artifacts = mock_get_artifacts
        mock_get_client.return_value = mock_client

        with patch.object(webhook_handler, "_upsert_artifact", new_callable=AsyncMock) as mock_upsert:
            await webhook_handler._handle_scanning_completed(event_data)
            assert mock_upsert.called


@pytest.mark.asyncio
async def test_webhook_handle_scanning_completed_missing_data():
    """Test handling of SCANNING_COMPLETED with missing repository data."""
    webhook_handler = HarborWebhookHandler()

    event_data = {"repository": {}}
    await webhook_handler._handle_scanning_completed(event_data)  # Should not raise


# Scanning Failed Handler Tests
@pytest.mark.asyncio
async def test_webhook_handle_scanning_failed():
    """Test handling of SCANNING_FAILED webhook event."""
    webhook_handler = HarborWebhookHandler()

    event_data = {"repository": {"namespace": "library", "name": "nginx"}}

    # Should not raise an error, just log warning
    await webhook_handler._handle_scanning_failed(event_data)
