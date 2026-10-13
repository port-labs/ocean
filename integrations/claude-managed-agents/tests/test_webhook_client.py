from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from clients.exceptions import WebhookSigningSecretNotConfiguredError
from clients.webhook_client import ClaudeWebhookClient, _WEBHOOK_EVENTS


@pytest.fixture
def webhook_http() -> MagicMock:
    return MagicMock()


@pytest.fixture
def webhook_client(webhook_http: MagicMock) -> ClaudeWebhookClient:
    return ClaudeWebhookClient(
        http_client=webhook_http,
        anthropic_client=MagicMock(),
        console_host="https://platform.claude.com",
        api_key="test-api-key",
        webhook_signing_secret="whsec_test",
        anthropic_version="2023-06-01",
    )


def test_signing_secret_name_uses_install_modal_prefix() -> None:
    client = ClaudeWebhookClient(
        http_client=MagicMock(),
        anthropic_client=MagicMock(),
        console_host="https://platform.claude.com",
        api_key="test-api-key",
    )
    with patch("clients.webhook_client.ocean") as mock_ocean:
        mock_ocean.config.integration.identifier = "claude-managed"
        mock_ocean.config.integration.type = "claude-managed-agents"
        assert (
            client._signing_secret_name()
            == "_CLAUDE_MANAGED_CLAUDE_MANAGED_AGENTS_WEBHOOK_SIGNING_SECRET"
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
    webhook_http: MagicMock,
) -> None:
    webhook_http.post = AsyncMock(
        return_value=httpx.Response(
            200,
            json={"id": "wh_new", "signing_secret": "whsec_once"},
            request=httpx.Request("POST", "https://platform.claude.com/v1/webhooks"),
        )
    )

    await webhook_client.upsert_webhook("https://ocean.example")

    webhook_http.post.assert_awaited_once()
    body = webhook_http.post.await_args.kwargs["json"]
    assert body["url"] == "https://ocean.example/integration/webhook"
    assert body["name"] == "Port Ocean Integration"
    assert "session.status_idled" in body["enabled_events"]
    assert "vault.deleted" in body["enabled_events"]


@pytest.mark.asyncio
async def test_upsert_webhook_reconciles_events_on_conflict(
    webhook_client: ClaudeWebhookClient,
    webhook_http: MagicMock,
) -> None:
    webhook_url = "https://ocean.example/integration/webhook"
    existing_events = ["session.status_idled", "agent.created"]
    webhook_http.post = AsyncMock(
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
    webhook_http.get = AsyncMock(
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

    assert webhook_http.post.await_count == 2
    webhook_http.get.assert_awaited_once()
    update_body = webhook_http.post.await_args_list[1].kwargs["json"]
    assert set(update_body["enabled_events"]) == set(existing_events) | set(
        _WEBHOOK_EVENTS
    )
    assert "agent.created" in update_body["enabled_events"]


@pytest.mark.asyncio
async def test_upsert_webhook_skips_update_when_events_cover_required(
    webhook_client: ClaudeWebhookClient,
    webhook_http: MagicMock,
) -> None:
    webhook_url = "https://ocean.example/integration/webhook"
    webhook_http.post = AsyncMock(
        return_value=httpx.Response(
            409,
            request=httpx.Request("POST", "https://platform.claude.com/v1/webhooks"),
        )
    )
    webhook_http.get = AsyncMock(
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

    webhook_http.post.assert_awaited_once()
    webhook_http.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_webhook_logs_api_errors(
    webhook_client: ClaudeWebhookClient,
    webhook_http: MagicMock,
) -> None:
    webhook_http.post = AsyncMock(
        return_value=httpx.Response(
            400,
            text='{"error":"bad"}',
            request=httpx.Request("POST", "https://platform.claude.com/v1/webhooks"),
        )
    )

    await webhook_client.upsert_webhook("https://ocean.example")

    webhook_http.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_webhook_persists_signing_secret_on_saas() -> None:
    http = MagicMock()
    client = ClaudeWebhookClient(
        http_client=http,
        anthropic_client=MagicMock(),
        console_host="https://platform.claude.com",
        api_key="test-api-key",
        webhook_signing_secret=None,
        verify_webhook_secrets=True,
    )
    http.post = AsyncMock(
        return_value=httpx.Response(
            200,
            json={"id": "wh_new", "signing_secret": "whsec_once"},
            request=httpx.Request("POST", "https://platform.claude.com/v1/webhooks"),
        )
    )

    with (
        patch.object(
            client, "_persist_signing_secret", new_callable=AsyncMock
        ) as persist,
        patch("clients.webhook_client.ocean") as mock_ocean,
    ):
        mock_ocean.app.is_saas = MagicMock(return_value=True)
        await client.upsert_webhook("https://ocean.example")

    persist.assert_awaited_once_with("whsec_once")
    assert client.has_webhook_secret is True


@pytest.mark.asyncio
async def test_upsert_webhook_skips_persist_when_not_saas() -> None:
    http = MagicMock()
    client = ClaudeWebhookClient(
        http_client=http,
        anthropic_client=MagicMock(),
        console_host="https://platform.claude.com",
        api_key="test-api-key",
        webhook_signing_secret=None,
        verify_webhook_secrets=True,
    )
    http.post = AsyncMock(
        return_value=httpx.Response(
            200,
            json={"id": "wh_new", "signing_secret": "whsec_once"},
            request=httpx.Request("POST", "https://platform.claude.com/v1/webhooks"),
        )
    )

    with (
        patch.object(
            client, "_persist_signing_secret", new_callable=AsyncMock
        ) as persist,
        patch("clients.webhook_client.ocean") as mock_ocean,
    ):
        mock_ocean.app.is_saas = MagicMock(return_value=False)
        await client.upsert_webhook("https://ocean.example")

    persist.assert_not_awaited()
    assert client.has_webhook_secret is True


@pytest.mark.asyncio
async def test_backfill_skips_when_org_secret_missing() -> None:
    client = ClaudeWebhookClient(
        http_client=MagicMock(),
        anthropic_client=MagicMock(),
        console_host="https://platform.claude.com",
        api_key="test-api-key",
        webhook_signing_secret=None,
        verify_webhook_secrets=True,
    )
    with patch("clients.webhook_client.ocean") as mock_ocean:
        mock_ocean.app.is_saas = MagicMock(return_value=True)
        mock_ocean.config.integration.identifier = "claude-managed"
        mock_ocean.config.integration.type = "claude-managed-agents"
        mock_ocean.port_client.get_organization_secret = AsyncMock(return_value=None)
        mock_ocean.port_client.patch_integration = AsyncMock()

        await client._backfill_signing_secret_spec_if_needed()

    mock_ocean.port_client.patch_integration.assert_not_awaited()


@pytest.mark.asyncio
async def test_backfill_patches_spec_when_org_secret_exists() -> None:
    client = ClaudeWebhookClient(
        http_client=MagicMock(),
        anthropic_client=MagicMock(),
        console_host="https://platform.claude.com",
        api_key="test-api-key",
        webhook_signing_secret=None,
        verify_webhook_secrets=True,
    )
    with patch("clients.webhook_client.ocean") as mock_ocean:
        mock_ocean.app.is_saas = MagicMock(return_value=True)
        mock_ocean.config.integration.identifier = "claude-managed"
        mock_ocean.config.integration.type = "claude-managed-agents"
        mock_ocean.port_client.get_organization_secret = AsyncMock(
            return_value={"secretName": "x"}
        )
        mock_ocean.port_client.patch_integration = AsyncMock()

        await client._backfill_signing_secret_spec_if_needed()

    mock_ocean.port_client.patch_integration.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_webhook_backfills_spec_on_conflict_when_secret_missing() -> None:
    http = MagicMock()
    client = ClaudeWebhookClient(
        http_client=http,
        anthropic_client=MagicMock(),
        console_host="https://platform.claude.com",
        api_key="test-api-key",
        webhook_signing_secret=None,
        verify_webhook_secrets=True,
    )
    webhook_url = "https://ocean.example/integration/webhook"
    http.post = AsyncMock(
        return_value=httpx.Response(
            409,
            request=httpx.Request("POST", "https://platform.claude.com/v1/webhooks"),
        )
    )
    http.get = AsyncMock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "wh_existing",
                        "url": webhook_url,
                        "enabled_events": list(_WEBHOOK_EVENTS),
                    }
                ]
            },
            request=httpx.Request("GET", "https://platform.claude.com/v1/webhooks"),
        )
    )

    with (
        patch.object(
            client, "_backfill_signing_secret_spec_if_needed", new_callable=AsyncMock
        ) as backfill,
        patch("clients.webhook_client.ocean") as mock_ocean,
    ):
        mock_ocean.app.is_saas = MagicMock(return_value=True)
        await client.upsert_webhook("https://ocean.example")

    backfill.assert_awaited_once()
