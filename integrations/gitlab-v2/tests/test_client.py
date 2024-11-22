import pytest
from typing import Any
from unittest import mock, IsolatedAsyncioTestCase

import httpx

from choices import Endpoint, Entity
from client import get_gitlab_handler
from tests import setup_ocean_context
from tests.data import API_DATA


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    setup_ocean_context()


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

    @mock.patch("client.http_async_client.request", new_callable=mock.AsyncMock)
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

    @mock.patch("client.http_async_client.request", new_callable=mock.AsyncMock)
    @mock.patch("client.asyncio.sleep", new_callable=mock.AsyncMock)
    async def test_rate_limit(
        self,
        mock_asyncio_sleep: mock.AsyncMock,
        mock_http_async_client: mock.AsyncMock,
    ):
        mock_response_headers = {
            "RateLimit-Limit": "60",
            "RateLimit-Name": "throttle_authenticated_web",
            "RateLimit-Observed": "67",
            "RateLimit-Remaining": "0",
            "RateLimit-Reset": "1609844400",
            "RateLimit-ResetTime": "Tue, 05 Jan 2021 11:00:00 GMT",
            "Retry-After": "30",
        }

        mock_http_async_client.return_value = httpx.Response(
            429,
            json={"message": "Rate limit exceeded."},
            headers=mock_response_headers,
            request=httpx.Request("GET", "test-endpoint"),
        )

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
        mock_asyncio_sleep.assert_called_with(int(mock_response_headers["Retry-After"]))

    @mock.patch(
        "client.GitLabHandler.send_gitlab_api_request", new_callable=mock.AsyncMock
    )
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

    @mock.patch(
        "client.GitLabHandler.send_gitlab_api_request", new_callable=mock.AsyncMock
    )
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
