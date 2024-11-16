from typing import Any
from unittest import mock, IsolatedAsyncioTestCase
from unittest.mock import patch

from aiolimiter import AsyncLimiter

from client import GitLabHandler
from choices import Endpoint, Entity
from tests.data import DATA
from tests.webhook_data import WEBHOOK_DATA


class ClientTest(IsolatedAsyncioTestCase):
    data: dict[str, Any] = DATA
    webhook_data: dict[str, Any] = WEBHOOK_DATA
    handler = GitLabHandler(
        host="http://localhost:8080",
        gitlab_token="secretsecret",
        gitlab_url="https://gitlab.com/api/v4",
        webhook_secret="personal_token",
        rate_limit=AsyncLimiter(5),
    )

    async def api_mocked(self, endpoint: str) -> list[dict[str, Any]]:
        if endpoint == Endpoint.GROUP.value:
            return self.data[Entity.GROUP.value]
        elif endpoint == Endpoint.PROJECT.value:
            return self.data[Entity.PROJECT.value]
        elif endpoint == Endpoint.MERGE_REQUEST.value:
            return self.data[Entity.MERGE_REQUEST.value]
        elif endpoint == Endpoint.ISSUE.value:
            return self.data[Entity.ISSUE.value]

        raise Exception

    @patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=mock.AsyncMock,
    )
    @patch("client.GitLabHandler.fetch_data", new_callable=mock.AsyncMock)
    async def test_fetch_data(
        self, mock_fetch_data: mock.AsyncMock, mock_integration_config: mock.AsyncMock
    ) -> None:
        mock_integration_config.return_value = {
            "gitlab_url": "http://localhost:8080",
            "gitlab_token": "test_token",
        }

        mock_fetch_data.side_effect = self.api_mocked

        fetched_groups = await self.handler.fetch_data(Endpoint.GROUP.value)

        self.assertEqual(fetched_groups, self.data[Entity.GROUP.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.GROUP.value)])

        mock_fetch_data.reset_mock()
        fetched_projects = await self.handler.fetch_data(Endpoint.PROJECT.value)

        self.assertEqual(fetched_projects, self.data[Entity.PROJECT.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.PROJECT.value)])

        mock_fetch_data.reset_mock()
        fetched_merged_requests = await self.handler.fetch_data(
            Endpoint.MERGE_REQUEST.value
        )

        self.assertEqual(fetched_merged_requests, self.data[Entity.MERGE_REQUEST.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.MERGE_REQUEST.value)])

        mock_fetch_data.reset_mock()
        fetched_issues = await self.handler.fetch_data(Endpoint.ISSUE.value)

        self.assertEqual(fetched_issues, self.data[Entity.ISSUE.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.ISSUE.value)])

    async def gitlab_data(self, endpoint: str) -> list[dict[str, Any]]:
        if Endpoint.GROUP.value == endpoint:
            return self.data[Entity.GROUP.value]
        elif Endpoint.PROJECT.value == endpoint:
            return self.data[Entity.PROJECT.value]
        elif Endpoint.MERGE_REQUEST.value == endpoint:
            return self.data[Entity.MERGE_REQUEST.value]
        elif Endpoint.ISSUE.value == endpoint:
            return self.data[Entity.ISSUE.value]

        raise Exception

    @patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=mock.AsyncMock,
    )
    @patch("client.GitLabHandler.create_webhook", new_callable=mock.AsyncMock)
    @patch("client.GitLabHandler.call_gitlab", new_callable=mock.AsyncMock)
    async def test_webhook_creation(
        self,
        mock_call_gitlab: mock.AsyncMock,
        mock_update_webhook: mock.AsyncMock,
        mock_integration_config: mock.AsyncMock,
    ) -> None:
        mock_integration_config.return_value = {
            "gitlab_url": "http://localhost:8080",
            "gitlab_token": "test_token",
        }

        mock_call_gitlab.side_effect = self.gitlab_data

        await self.handler.fetch_data(Endpoint.GROUP.value)
        mock_update_webhook.assert_called()

        mock_update_webhook.reset_mock()
        await self.handler.fetch_data(Endpoint.PROJECT.value)
        mock_update_webhook.assert_not_called()

        mock_update_webhook.reset_mock()
        await self.handler.fetch_data(Endpoint.MERGE_REQUEST.value)
        mock_update_webhook.assert_not_called()

        mock_update_webhook.reset_mock()
        await self.handler.fetch_data(Endpoint.ISSUE.value)
        mock_update_webhook.assert_not_called()

    async def gitlab_data_by_id(self, url: str) -> list[dict[str, Any]]:
        entity_endpoint = url.split("/")[-2]
        if entity_endpoint in Endpoint.GROUP.value:
            return self.data[Entity.GROUP.value][0]
        elif entity_endpoint in Endpoint.PROJECT.value:
            return self.data[Entity.PROJECT.value][0]
        elif entity_endpoint in Endpoint.MERGE_REQUEST.value:
            return self.data[Entity.MERGE_REQUEST.value][0]
        elif entity_endpoint in Endpoint.ISSUE.value:
            return self.data[Entity.ISSUE.value][0]

        raise Exception

    @patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=mock.MagicMock,
    )
    @patch("client.GitLabHandler.call_gitlab", new_callable=mock.AsyncMock)
    async def test_webhook_handler(
        self,
        mock_call_gitlab: mock.AsyncMock,
        mock_integration_config: mock.AsyncMock,
    ) -> None:
        mock_integration_config.return_value = {
            "gitlab_url": "http://localhost:8080",
            "gitlab_token": "test_token",
        }
        mock_call_gitlab.side_effect = self.gitlab_data_by_id

        await self.handler.system_hook_group_handler(
            self.webhook_data[Entity.GROUP.value]
        )
        mock_call_gitlab.assert_called()

        mock_call_gitlab.reset_mock()
        await self.handler.system_hook_project_handler(
            self.webhook_data[Entity.PROJECT.value]
        )
        mock_call_gitlab.assert_called()

        mock_call_gitlab.reset_mock()
        await self.handler.merge_request_handler(
            self.webhook_data[Entity.MERGE_REQUEST.value]
        )
        mock_call_gitlab.assert_called()

        mock_call_gitlab.reset_mock()
        await self.handler.issue_handler(self.webhook_data[Entity.ISSUE.value])
        mock_call_gitlab.assert_called()
