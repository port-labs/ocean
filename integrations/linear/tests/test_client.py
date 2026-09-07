from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

from linear.client import LinearClient
from linear.core.exporters import DocumentExporter
from linear.core.exporters.document_exporter import GetDocumentOptions
from linear.webhook.webhook_client import LinearWebhookClient


@pytest.fixture
def linear_client() -> LinearClient:
    return LinearClient("test-api-key")


@pytest.mark.asyncio
class TestLinearWebhookClient:
    async def test_create_events_webhook_updates_existing_webhook(
        self, linear_client: LinearClient
    ) -> None:
        webhook_client = LinearWebhookClient(linear_client)
        mock_execute = AsyncMock(
            side_effect=[
                {
                    "webhooks": {
                        "nodes": [
                            {
                                "id": "webhook-1",
                                "url": "https://app.getport.io/integration/webhook",
                            }
                        ]
                    }
                },
                {},
            ]
        )

        with patch.object(linear_client.graphql, "execute", mock_execute):
            await webhook_client.create_events_webhook("https://app.getport.io")

        assert mock_execute.await_count == 2
        assert "webhookUpdate" in mock_execute.await_args_list[1].args[0]
        assert "webhook-1" in mock_execute.await_args_list[1].args[0]


@pytest.mark.asyncio
class TestDocumentExporter:
    async def test_get_paginated_resources(self, linear_client: LinearClient) -> None:
        exporter = DocumentExporter(linear_client)
        first_page = [
            {"id": "doc-1", "title": "project-readme"},
            {"id": "doc-2", "title": "payment-service-prd"},
        ]
        second_page = [{"id": "doc-3", "title": "test-project-docs"}]

        async def mock_paginate(
            *_args: object, **_kwargs: object
        ) -> AsyncGenerator[list[dict[str, str]], None]:
            yield first_page
            yield second_page

        with patch.object(
            exporter, "_paginate_graphql_objects", side_effect=mock_paginate
        ):
            results = [
                batch async for batch in exporter.get_paginated_resources()
            ]

        assert len(results) == 2
        assert results[0] == first_page
        assert results[1] == second_page

    async def test_get_resource(self, linear_client: LinearClient) -> None:
        exporter = DocumentExporter(linear_client)
        options = GetDocumentOptions(resource_id="50e3e770-03ef-4c12-9f5a-e3122a768bc4")
        document = {
            "id": "50e3e770-03ef-4c12-9f5a-e3122a768bc4",
            "title": "payment-service-prd",
            "project": {"id": "project-1", "name": "Surveys"},
        }
        mock_execute_template = AsyncMock(return_value={"document": document})

        with patch.object(
            linear_client.graphql, "execute_query_template", mock_execute_template
        ):
            result = await exporter.get_resource(options)

        assert result == document
        mock_execute_template.assert_awaited_once()
