import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from datadog.client import DatadogClient
from datadog.webhook.webhook_client import (
    DatadogWebhookClient,
    PORT_AUTH_HEADER_NAME,
    _PORT_MONITOR_NOTIFICATION_RULE_NAME,
)


@pytest.mark.asyncio
async def test_create_webhook_and_append_recipient_when_webhook_is_new(
    mock_datadog_client: DatadogClient,
) -> None:
    webhook_client = DatadogWebhookClient(mock_datadog_client)
    with patch.object(
        webhook_client.client, "send_api_request", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = [
            httpx.HTTPStatusError(
                "not found",
                request=httpx.Request(
                    "GET",
                    "https://api.datadoghq.com/api/v1/integration/webhooks/configuration/webhooks/org_123-dd-integration",
                ),
                response=httpx.Response(
                    404,
                    request=httpx.Request(
                        "GET",
                        "https://api.datadoghq.com/api/v1/integration/webhooks/configuration/webhooks/org_123-dd-integration",
                    ),
                ),
            ),
            {"status": "created"},
            {"data": []},
            {"status": "created"},
        ]
        base_url = "https://example.com"
        webhook_secret = "test_secret"
        org_id = "org_123"
        integration_identifier = "dd-integration"
        monitor_webhook_name = f"{org_id}-{integration_identifier}"

        await webhook_client.upsert_webhook_setup(
            base_url=base_url,
            webhook_secret=webhook_secret,
            org_id=org_id,
            integration_identifier=integration_identifier,
        )

        assert mock_send.await_count == 4

        get_webhook_call = mock_send.await_args_list[0].kwargs
        assert get_webhook_call.get("method", "GET") == "GET"
        assert get_webhook_call["url"].endswith(
            f"/api/v1/integration/webhooks/configuration/webhooks/{monitor_webhook_name}"
        )

        webhook_call = mock_send.await_args_list[1].kwargs
        assert webhook_call["method"] == "POST"
        assert webhook_call["url"].endswith(
            "/api/v1/integration/webhooks/configuration/webhooks"
        )
        assert (
            webhook_call["json_data"]["url"]
            == "https://example.com/integration/webhook/monitor-events"
        )
        assert json.loads(webhook_call["json_data"]["custom_headers"]) == {
            PORT_AUTH_HEADER_NAME: webhook_secret
        }
        assert webhook_call["json_data"]["custom_headers"] == json.dumps(
            {
                PORT_AUTH_HEADER_NAME: webhook_secret,
            }
        )

        monitor_rule_create_call = mock_send.await_args_list[3].kwargs
        assert monitor_rule_create_call["method"] == "POST"
        assert monitor_rule_create_call["json_data"]["data"]["attributes"]["name"] == (
            _PORT_MONITOR_NOTIFICATION_RULE_NAME
        )
        assert monitor_rule_create_call["json_data"]["data"]["attributes"][
            "recipients"
        ] == [f"webhook-{monitor_webhook_name}"]


@pytest.mark.asyncio
async def test_skip_webhook_update_when_config_is_unchanged(
    mock_datadog_client: DatadogClient,
) -> None:
    webhook_client = DatadogWebhookClient(mock_datadog_client)
    webhook_name = "org_123-dd-integration"
    base_url = "https://example.com"
    secret = "test_secret"
    current_url = f"{base_url}/integration/webhook/monitor-events"
    current_headers = json.dumps({PORT_AUTH_HEADER_NAME: secret})

    from datadog.webhook.webhook_client import _WEBHOOK_PAYLOAD_TEMPLATE

    with patch.object(
        webhook_client.client, "send_api_request", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = [
            {
                "name": webhook_name,
                "url": current_url,
                "custom_headers": current_headers,
                "payload": _WEBHOOK_PAYLOAD_TEMPLATE,
            },
            {"data": []},
            {"status": "created"},
        ]

        await webhook_client.upsert_webhook_setup(
            base_url=base_url,
            webhook_secret=secret,
            org_id="org_123",
            integration_identifier="dd-integration",
        )

        # no PUT — GET webhook + GET rules + POST rule
        assert mock_send.await_count == 3
        methods = [c.kwargs.get("method", "GET") for c in mock_send.await_args_list]
        assert "PUT" not in methods


@pytest.mark.asyncio
async def test_update_webhook_config_and_append_recipient_when_webhook_already_exists(
    mock_datadog_client: DatadogClient,
) -> None:
    webhook_client = DatadogWebhookClient(mock_datadog_client)
    webhook_name = "org_123-dd-integration"
    new_base_url = "https://new-url.example.com"
    new_secret = "new_secret"

    with patch.object(
        webhook_client.client, "send_api_request", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = [
            {
                "name": webhook_name,
                "url": "https://old-url.example.com/integration/webhook/monitor-events",
            },
            {"status": "updated"},
            {"data": []},
            {"status": "created"},
        ]

        await webhook_client.upsert_webhook_setup(
            base_url=new_base_url,
            webhook_secret=new_secret,
            org_id="org_123",
            integration_identifier="dd-integration",
        )

        # GET webhook-by-name, PUT update, GET rules, POST new rule
        assert mock_send.await_count == 4

        update_call = mock_send.await_args_list[1].kwargs
        assert update_call["method"] == "PUT"
        assert update_call["url"].endswith(
            f"/api/v1/integration/webhooks/configuration/webhooks/{webhook_name}"
        )
        assert (
            update_call["json_data"]["url"] == f"{new_base_url}/integration/webhook/monitor-events"
        )
        assert json.loads(update_call["json_data"]["custom_headers"]) == {
            PORT_AUTH_HEADER_NAME: new_secret
        }

        post_rule_call = mock_send.await_args_list[3].kwargs
        assert post_rule_call["method"] == "POST"
        assert post_rule_call["json_data"]["data"]["attributes"]["recipients"] == [
            f"webhook-{webhook_name}"
        ]


@pytest.mark.asyncio
async def test_create_webhook_without_secret_omits_custom_headers(
    mock_datadog_client: DatadogClient,
) -> None:
    webhook_client = DatadogWebhookClient(mock_datadog_client)
    with patch.object(
        webhook_client.client, "send_api_request", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = [
            httpx.HTTPStatusError(
                "not found",
                request=httpx.Request(
                    "GET",
                    "https://api.datadoghq.com/api/v1/integration/webhooks/configuration/webhooks/org_123-dd-integration",
                ),
                response=httpx.Response(
                    404,
                    request=httpx.Request(
                        "GET",
                        "https://api.datadoghq.com/api/v1/integration/webhooks/configuration/webhooks/org_123-dd-integration",
                    ),
                ),
            ),
            {"status": "created"},
            {"data": []},
            {"status": "created"},
        ]

        await webhook_client.upsert_webhook_setup(
            base_url="https://example.com",
            webhook_secret=None,
            org_id="org_123",
            integration_identifier="dd-integration",
        )

        webhook_call = mock_send.await_args_list[1].kwargs
        assert webhook_call["method"] == "POST"
        assert "custom_headers" not in webhook_call["json_data"]


@pytest.mark.asyncio
async def test_notification_rule_recipient_not_duplicated_when_already_present(
    mock_datadog_client: DatadogClient,
) -> None:
    webhook_client = DatadogWebhookClient(mock_datadog_client)
    rule_name = _PORT_MONITOR_NOTIFICATION_RULE_NAME
    recipient = "webhook-org_123-dd-integration"

    with patch.object(
        webhook_client.client, "send_api_request", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = [
            {
                "data": [
                    {
                        "id": "rule-1",
                        "attributes": {
                            "name": rule_name,
                            "recipients": [recipient],
                        },
                    }
                ]
            }
        ]

        await webhook_client._sync_notification_rule_recipient("org_123-dd-integration")

    # only the initial GET — no PATCH because recipient already present
    assert mock_send.await_count == 1
    methods = [c.kwargs.get("method", "GET") for c in mock_send.await_args_list]
    assert "PATCH" not in methods


@pytest.mark.asyncio
async def test_notification_rule_new_recipient_appended_to_existing_rule(
    mock_datadog_client: DatadogClient,
) -> None:
    webhook_client = DatadogWebhookClient(mock_datadog_client)
    rule_name = _PORT_MONITOR_NOTIFICATION_RULE_NAME
    existing_recipient = "webhook-other-integration"
    new_recipient = "webhook-org_123-dd-integration"

    with patch.object(
        webhook_client.client, "send_api_request", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = [
            {
                "data": [
                    {
                        "id": "rule-1",
                        "attributes": {
                            "name": rule_name,
                            "recipients": [existing_recipient],
                        },
                    }
                ]
            },
            {"status": "updated"},
        ]

        await webhook_client._sync_notification_rule_recipient("org_123-dd-integration")

    assert mock_send.await_count == 2
    patch_call = mock_send.await_args_list[1].kwargs
    assert patch_call["method"] == "PATCH"
    assert patch_call["json_data"]["data"]["attributes"]["recipients"] == [
        existing_recipient,
        new_recipient,
    ]


@pytest.mark.asyncio
async def test_notification_rule_created_when_missing(
    mock_datadog_client: DatadogClient,
) -> None:
    webhook_client = DatadogWebhookClient(mock_datadog_client)
    with patch.object(
        webhook_client.client, "send_api_request", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = [{"data": []}, {"status": "created"}]

        await webhook_client._sync_notification_rule_recipient("org_123-dd-integration")

    post_call = mock_send.await_args_list[1].kwargs
    assert post_call["method"] == "POST"
    assert post_call["json_data"]["data"]["attributes"]["recipients"] == [
        "webhook-org_123-dd-integration"
    ]


@pytest.mark.asyncio
async def test_find_existing_webhook_by_name_returns_none_on_404(
    mock_datadog_client: DatadogClient,
) -> None:
    webhook_client = DatadogWebhookClient(mock_datadog_client)
    with patch.object(
        webhook_client.client, "send_api_request", new_callable=AsyncMock
    ) as mock_send:
        request = httpx.Request(
            "GET",
            "https://api.datadoghq.com/api/v1/integration/webhooks/configuration/webhooks/missing",
        )
        mock_send.side_effect = httpx.HTTPStatusError(
            "not found", request=request, response=httpx.Response(404, request=request)
        )

        result = await webhook_client._find_existing_webhook(webhook_name="missing")

    assert result is None
