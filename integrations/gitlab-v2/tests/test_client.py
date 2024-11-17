import pytest

from typing import Any
from unittest import mock, IsolatedAsyncioTestCase
from unittest.mock import patch

from choices import Endpoint, Entity
from client import get_gitlab_handler, WebhookEventHandler
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from tests.data import API_DATA
from tests.webhook_data import WEBHOOK_DATA


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = mock.MagicMock()
        mock_ocean_app.config.integration.config = {
            "app_host": "http://gitlab.com/api/v4",
            "gitlab_token": "tokentoken",
            "gitlab_url": "http://gitlab.com/api/v4",
            "webhook_secret": "secretsecret",
        }
        mock_ocean_app.integration_router = mock.MagicMock()
        mock_ocean_app.port_client = mock.MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


class GitlabClientTest(IsolatedAsyncioTestCase):
    async def gitlab_data_mocked(self, endpoint: str, **kwargs) -> list[dict[str, Any]]:
        if endpoint == Endpoint.GROUP.value:
            return API_DATA[Entity.GROUP.value]
        elif endpoint == Endpoint.PROJECT.value:
            return API_DATA[Entity.PROJECT.value]
        elif endpoint == Endpoint.MERGE_REQUEST.value:
            return API_DATA[Entity.MERGE_REQUEST.value]
        elif endpoint == Endpoint.ISSUE.value:
            return API_DATA[Entity.ISSUE.value]

        raise Exception

    @patch("client.http_async_client.request", new_callable=mock.AsyncMock)
    async def test_send_api_request(self, mock_http_async_client: mock.AsyncMock):
        handler = await get_gitlab_handler()

        await handler.send_gitlab_api_request("get-endpoint")
        mock_http_async_client.assert_has_calls(
            [
                mock.call(
                    headers={"Authorization": "Bearer tokentoken"},
                    json={},
                    method="GET",
                    url="http://gitlab.com/api/v4/get-endpoint",
                )
            ]
        )

        await handler.send_gitlab_api_request(
            "post-endpoint", method="POST", payload={"key": "value"}
        )
        mock_http_async_client.assert_has_calls(
            [
                mock.call(
                    headers={"Authorization": "Bearer tokentoken"},
                    json={"key": "value"},
                    method="POST",
                    url="http://gitlab.com/api/v4/post-endpoint",
                )
            ]
        )

    @patch("client.GitLabHandler.send_gitlab_api_request", new_callable=mock.AsyncMock)
    async def test_fetch_entity(self, mock_fetch_data: mock.AsyncMock):
        handler = await get_gitlab_handler()

        mock_fetch_data.side_effect = self.gitlab_data_mocked

        fetched_groups = await handler.send_gitlab_api_request(Endpoint.GROUP.value)

        self.assertEqual(fetched_groups, API_DATA[Entity.GROUP.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.GROUP.value)])

        fetched_projects = await handler.send_gitlab_api_request(Endpoint.PROJECT.value)

        self.assertEqual(fetched_projects, API_DATA[Entity.PROJECT.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.PROJECT.value)])

        fetched_merged_requests = await handler.send_gitlab_api_request(
            Endpoint.MERGE_REQUEST.value
        )

        self.assertEqual(fetched_merged_requests, API_DATA[Entity.MERGE_REQUEST.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.MERGE_REQUEST.value)])

        fetched_issues = await handler.send_gitlab_api_request(Endpoint.ISSUE.value)

        self.assertEqual(fetched_issues, API_DATA[Entity.ISSUE.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.ISSUE.value)])

    @patch("client.GitLabHandler.send_gitlab_api_request", new_callable=mock.AsyncMock)
    async def test_create_webhook(self, mock_fetch_data: mock.AsyncMock):
        mock_fetch_data.return_value = []

        handler = await get_gitlab_handler()
        await handler.create_webhook(group_id="test-id")

        mock_fetch_data.assert_has_calls(
            [
                mock.call("groups/test-id/hooks"),
                mock.call(
                    "groups/test-id/hooks",
                    method="POST",
                    payload={
                        "url": "http://gitlab.com/api/v4/integration/webhook",
                        "custom_headers": [
                            {"key": "port-headers", "value": "secretsecret"}
                        ],
                        "issues_events": True,
                        "merge_requests_events": True,
                    },
                ),
            ]
        )


class WebhookHandlerTest(IsolatedAsyncioTestCase):
    @patch("client.GitLabHandler.send_gitlab_api_request", new_callable=mock.AsyncMock)
    async def test_data_handler(self, mock_fetch_data: mock.AsyncMock):
        mock_fetch_data.return_value = []

        handler = await get_gitlab_handler()
        webhook_handler = WebhookEventHandler(handler)

        await webhook_handler.merge_request_handler(
            data=WEBHOOK_DATA[Entity.MERGE_REQUEST.value]
        )
        mock_fetch_data.assert_called_with("projects/1/merge_requests/1")

        await webhook_handler.issue_handler(data=WEBHOOK_DATA[Entity.ISSUE.value])
        mock_fetch_data.assert_called_with("projects/1/issues/23")

        await webhook_handler.system_hook_project_handler(
            data=WEBHOOK_DATA[Entity.PROJECT.value]
        )
        mock_fetch_data.assert_called_with("projects/74")

        await webhook_handler.system_hook_group_handler(
            data=WEBHOOK_DATA[Entity.GROUP.value]
        )
        mock_fetch_data.assert_called_with("groups/78")
