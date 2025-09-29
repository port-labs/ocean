import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from okta.webhook_processors.webhook_client import OktaWebhookClient


@pytest.mark.asyncio
async def test_ensure_event_hook_idempotent_and_verifies() -> None:
    client = OktaWebhookClient(okta_domain="example.okta.com", api_token="t")  # type: ignore[arg-type]

    async def list_event_hooks_pages():
        yield [
            {"channel": {"config": {"uri": "https://app.example.com/integration/webhook"}}}
        ]

    client.send_paginated_request = MagicMock(return_value=list_event_hooks_pages())  # type: ignore[assignment]

    with patch("okta.webhook_processors.webhook_client.ocean") as ocean_mock:
        ocean_mock.integration_config = {"webhook_secret": "secret-123"}

        # First: exists -> no creation
        await client.ensure_event_hook("https://app.example.com")

        # Now: no existing hook -> should create and verify
        async def empty_pages():
            if False:
                yield []  # pragma: no cover

            return

        client.send_paginated_request = MagicMock(return_value=empty_pages())  # type: ignore[assignment]

        created_resp = MagicMock()
        created_resp.json.return_value = {
            "_links": {"verify": {"href": "https://example.okta.com/api/v1/eventHooks/1/verify"}}
        }

        client.make_request = AsyncMock(side_effect=[created_resp, MagicMock()])

        await client.ensure_event_hook("https://app.example.com/")

        assert client.make_request.await_count == 2
        first_args = client.make_request.await_args_list[0].kwargs
        assert first_args["method"] == "POST"
        assert first_args["json_data"]["channel"]["config"]["authScheme"]["value"] == "secret-123"


