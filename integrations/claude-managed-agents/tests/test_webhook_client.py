from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from clients.exceptions import WebhookSigningSecretNotConfiguredError
from clients.webhook_client import ClaudeWebhookClient, _WEBHOOK_EVENTS


@pytest.fixture
def webhook_client() -> ClaudeWebhookClient:
    http = MagicMock()
    anthropic = MagicMock()
    return ClaudeWebhookClient(
        http_client=http,
        anthropic_client=anthropic,
        console_host="https://platform.claude.com",
        api_key="test-api-key",
        webhook_signing_secret="whsec_test",
        anthropic_version="2023-06-01",
    )


def test_unwrap_webhook_without_secret_raises() -> None:
    client = ClaudeWebhookClient(
        http_client=MagicMock(),
        anthropic_client=MagicMock(),
        console_host="https://platform.claude.com",
        api_key="test-api-key",
        webhook_signing_secret=None,
    )
    assert client.has_webhook_secret is False
    with pytest.raises(WebhookSigningSecretNotConfiguredError):
        client.unwrap_webhook("{}", {})


@pytest.mark.asyncio
async def test_upsert_webhook_creates(
    webhook_client: ClaudeWebhookClient,
) -> None:
    webhook_client._http.post = AsyncMock(
        return_value=httpx.Response(
            200,
            json={"id": "wh_new", "signing_secret": "whsec_once"},
            request=httpx.Request("POST", "https://platform.claude.com/v1/webhooks"),
        )
    )

    await webhook_client.upsert_webhook("https://ocean.example")

    webhook_client._http.post.assert_awaited_once()
    body = webhook_client._http.post.await_args.kwargs["json"]
    assert body["url"] == "https://ocean.example/integration/webhook"
    assert body["name"] == "Port Ocean Integration"
    assert "session.status_idled" in body["enabled_events"]
    assert "vault.deleted" in body["enabled_events"]


@pytest.mark.asyncio
async def test_upsert_webhook_reconciles_events_on_conflict(
    webhook_client: ClaudeWebhookClient,
) -> None:
    webhook_url = "https://ocean.example/integration/webhook"
    existing_events = ["session.status_idled", "agent.created"]
    webhook_client._http.post = AsyncMock(
        side_effect=[
            httpx.Response(
                409,
                request=httpx.Request(
                    "POST", "https://platform.claude.com/v1/webhooks"
                ),
            ),
            httpx.Response(
                200,
                json={"id": "wh_existing"},
                request=httpx.Request(
                    "POST", "https://platform.claude.com/v1/webhooks/wh_existing"
                ),
            ),
        ]
    )
    webhook_client._http.get = AsyncMock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "wh_existing",
                        "url": webhook_url,
                        "enabled_events": existing_events,
                    }
                ]
            },
            request=httpx.Request("GET", "https://platform.claude.com/v1/webhooks"),
        )
    )

    await webhook_client.upsert_webhook("https://ocean.example")

    assert webhook_client._http.post.await_count == 2
    webhook_client._http.get.assert_awaited_once()
    update_body = webhook_client._http.post.await_args_list[1].kwargs["json"]
    assert set(update_body["enabled_events"]) == set(existing_events) | set(
        _WEBHOOK_EVENTS
    )
    assert "agent.created" in update_body["enabled_events"]


@pytest.mark.asyncio
async def test_upsert_webhook_skips_update_when_events_cover_required(
    webhook_client: ClaudeWebhookClient,
) -> None:
    webhook_url = "https://ocean.example/integration/webhook"
    webhook_client._http.post = AsyncMock(
        return_value=httpx.Response(
            409,
            request=httpx.Request("POST", "https://platform.claude.com/v1/webhooks"),
        )
    )
    webhook_client._http.get = AsyncMock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "wh_existing",
                        "url": webhook_url,
                        "enabled_events": [*_WEBHOOK_EVENTS, "agent.created"],
                    }
                ]
            },
            request=httpx.Request("GET", "https://platform.claude.com/v1/webhooks"),
        )
    )

    await webhook_client.upsert_webhook("https://ocean.example")

    webhook_client._http.post.assert_awaited_once()
    webhook_client._http.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_webhook_logs_api_errors(
    webhook_client: ClaudeWebhookClient,
) -> None:
    webhook_client._http.post = AsyncMock(
        return_value=httpx.Response(
            400,
            text='{"error":"bad"}',
            request=httpx.Request("POST", "https://platform.claude.com/v1/webhooks"),
        )
    )

    await webhook_client.upsert_webhook("https://ocean.example")

    webhook_client._http.post.assert_awaited_once()
