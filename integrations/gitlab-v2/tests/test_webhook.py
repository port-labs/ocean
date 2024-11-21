import pytest
from unittest import mock, IsolatedAsyncioTestCase

from choices import Entity
from client import get_gitlab_handler
from tests import setup_ocean_context
from tests.webhook_data import WEBHOOK_DATA
from webhook import WebhookEventHandler


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    setup_ocean_context()


class WebhookHandlerTest(IsolatedAsyncioTestCase):
    @mock.patch(
        "client.GitLabHandler.send_gitlab_api_request", new_callable=mock.AsyncMock
    )
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
