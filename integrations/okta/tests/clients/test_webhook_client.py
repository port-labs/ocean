import pytest
from typing import AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from okta.webhook_processors.webhook_client import OktaWebhookClient


@pytest.mark.asyncio
async def test_ensure_event_hook_idempotent_and_verifies() -> None:
    client = OktaWebhookClient(okta_domain="example.okta.com", api_token="t")

    async def list_event_hooks_pages() -> (
        AsyncGenerator[List[Dict[str, Dict[str, Dict[str, str]]]], None]
    ):
        yield [
            {
                "channel": {
                    "config": {"uri": "https://app.example.com/integration/webhook"}
                }
            }
        ]

    with patch.object(
        client, "send_paginated_request", return_value=list_event_hooks_pages()
    ):
        with patch("okta.webhook_processors.webhook_client.ocean") as ocean_mock:
            ocean_mock.integration_config = {"webhook_secret": "secret-123"}
            # First: exists -> no creation
            await client.ensure_event_hook("https://app.example.com")

    async def empty_pages() -> AsyncGenerator[List[Dict[str, str]], None]:
        if False:
            yield []  # pragma: no cover
        return

    with patch.object(client, "send_paginated_request", return_value=empty_pages()):
        with patch.object(client, "make_request", new_callable=AsyncMock) as mock_req:
            created_resp: MagicMock = MagicMock()
            created_resp.json.return_value = {
                "_links": {
                    "verify": {
                        "href": "https://example.okta.com/api/v1/eventHooks/1/verify"
                    }
                }
            }
            mock_req.side_effect = [created_resp, MagicMock()]

            with patch("okta.webhook_processors.webhook_client.ocean") as ocean_mock:
                ocean_mock.integration_config = {"webhook_secret": "secret-123"}
                await client.ensure_event_hook("https://app.example.com/")

            assert mock_req.await_count == 2
            first_args = mock_req.await_args_list[0].kwargs
            assert first_args["method"] == "POST"
            assert (
                first_args["json_data"]["channel"]["config"]["authScheme"]["value"]
                == "secret-123"
            )
