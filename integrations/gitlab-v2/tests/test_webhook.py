import pytest
from typing import Any
from unittest import mock, IsolatedAsyncioTestCase

from httpx._models import Response as HttpxResponse

from choices import Endpoint, Entity
from client import get_gitlab_handler
from tests import setup_ocean_context
from tests.data import API_DATA
from tests.webhook_data import WEBHOOK_DATA
from webhook import WebhookEventHandler


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    setup_ocean_context()


class WebhookHandlerTest(IsolatedAsyncioTestCase):
    async def gitlab_data_mocked(
        self, endpoint: str, **kwargs: dict[str, Any]
    ) -> HttpxResponse:
        entity_endpoint = endpoint.split("/")[-2]

        match entity_endpoint:
            case Endpoint.GROUP.value:
                return HttpxResponse(status_code=200, json=API_DATA[Entity.GROUP.value])
            case "projects":
                return HttpxResponse(
                    status_code=200, json=API_DATA[Entity.PROJECT.value]
                )
            case Endpoint.MERGE_REQUEST.value:
                return HttpxResponse(
                    status_code=200, json=API_DATA[Entity.MERGE_REQUEST.value]
                )
            case Endpoint.ISSUE.value:
                return HttpxResponse(status_code=200, json=API_DATA[Entity.ISSUE.value])
            case _:
                raise Exception

    @mock.patch(
        "client.GitLabHandler.send_gitlab_api_request", new_callable=mock.AsyncMock
    )
    async def test_data_handler(self, mock_fetch_data: mock.AsyncMock) -> None:
        mock_fetch_data.side_effect = self.gitlab_data_mocked

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
