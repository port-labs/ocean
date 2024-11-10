from typing import Any
from unittest import mock, IsolatedAsyncioTestCase
from unittest.mock import patch

from client import GitLabHandler
from choices import Endpoint, Entity
from tests.data import DATA
from tests.webhook_data import WEBHOOK_DATA


class ClientTest(IsolatedAsyncioTestCase):
    data: dict[str, Any] = DATA
    webhook_data: dict[str, Any] = WEBHOOK_DATA

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
    async def test_fetch_data(self, mock_fetch_data: mock.AsyncMock, mock_integration_config: mock.AsyncMock) -> None:
        mock_integration_config.return_value = {
            "gitlab_url": "http://localhost:8080",
            "gitlab_token": "test_token",
        }

        mock_fetch_data.side_effect = self.api_mocked

        handler = GitLabHandler()

        fetched_groups = await handler.fetch_data(Endpoint.GROUP.value)

        self.assertEqual(fetched_groups, self.data[Entity.GROUP.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.GROUP.value)])

        fetched_projects = await handler.fetch_data(Endpoint.PROJECT.value)

        self.assertEqual(fetched_projects, self.data[Entity.PROJECT.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.PROJECT.value)])

        fetched_merged_requests = await handler.fetch_data(Endpoint.MERGE_REQUEST.value)

        self.assertEqual(fetched_merged_requests, self.data[Entity.MERGE_REQUEST.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.MERGE_REQUEST.value)])

        fetched_issues = await handler.fetch_data(Endpoint.ISSUE.value)

        self.assertEqual(fetched_issues, self.data[Entity.ISSUE.value])
        mock_fetch_data.assert_has_calls([mock.call(Endpoint.ISSUE.value)])

    @patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=mock.AsyncMock,
    )
    @patch("client.ocean.register_raw", new_callable=mock.AsyncMock)
    async def test_webhook_handler(self, mock_register_raw: mock.AsyncMock, mock_integration_config: mock.AsyncMock) -> None:
        mock_integration_config.return_value = {
            "gitlab_url": "http://localhost:8080",
            "gitlab_token": "test_token",
            "gitlab_secret": "secretsecret",
        }

        handler = GitLabHandler()

        await handler.group_handler(self.webhook_data[Entity.GROUP.value])
        mock_register_raw.assert_called_with(
            Entity.GROUP.value,
            [{'id': 78, 'name': 'StoreCloud', 'description': 'storecloud'}],
        )

        await handler.project_handler(self.webhook_data[Entity.PROJECT.value])
        mock_register_raw.assert_called_with(
            Entity.PROJECT.value,
            [{'id': 74, 'name': 'StoreCloud', 'description': 'storecloud', 'path_with_namespace': 'jsmith/storecloud'}]
        )

        await handler.merge_request_handler(self.webhook_data[Entity.MERGE_REQUEST.value])
        mock_register_raw.assert_called_with(
            Entity.MERGE_REQUEST.value,
            [{'id': 99, 'title': 'MS-Viewport', 'author': {'name': 'Administrator'}, 'state': 'opened', 'created_at': '2013-12-03T17:23:34.000000Z', 'updated_at': '2013-12-03T17:23:34.000000Z', 'web_url': 'http://example.com/diaspora/merge_requests/1', 'reviewers': [{'id': 6, 'name': 'User1', 'username': 'user1', 'avatar_url': 'http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40&d=identicon'}], 'project_id': 1}]
        )

        await handler.issue_handler(self.webhook_data[Entity.ISSUE.value])
        mock_register_raw.assert_called_with(
            Entity.ISSUE.value,
            [{'id': 301, 'title': 'New API: create/update/delete file', 'web_url': 'http://example.com/diaspora/issues/23', 'description': 'Create new API for manipulations with repository', 'created_at': '2013-12-03T17:15:43.000000Z', 'updated_at': '2013-12-03T17:15:43.000000Z', 'author': {'id': 1, 'name': 'Administrator', 'username': 'root', 'avatar_url': 'http://www.gravatar.com/avatar/e64c7d89f26bd1972efa854d13d7dd61?s=40&d=identicon', 'email': 'admin@example.com'}, 'state': 'opened', 'labels': ['API'], 'project_id': 14}]
        )
