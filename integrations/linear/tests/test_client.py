from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linear.client import LinearClient


@pytest.fixture
def linear_client() -> LinearClient:
    mock_http = MagicMock()
    mock_http.headers = {}
    with patch("linear.client.http_async_client", mock_http):
        return LinearClient("test-api-key")


@pytest.mark.asyncio
class TestLinearDocumentClient:
    async def test_get_paginated_documents(self, linear_client: LinearClient) -> None:
        first_page = {
            "data": {
                "documents": {
                    "edges": [
                        {"node": {"id": "doc-1", "title": "project-readme"}},
                        {"node": {"id": "doc-2", "title": "payment-service-prd"}},
                    ],
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
                }
            }
        }
        second_page = {
            "data": {
                "documents": {
                    "edges": [{"node": {"id": "doc-3", "title": "test-project-docs"}}],
                    "pageInfo": {"hasNextPage": False, "endCursor": "cursor-2"},
                }
            }
        }

        with patch.object(
            linear_client, "_get_paginated_objects", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = [first_page, second_page]
            results = [batch async for batch in linear_client.get_paginated_documents()]

        assert len(results) == 2
        assert results[0] == [
            {"id": "doc-1", "title": "project-readme"},
            {"id": "doc-2", "title": "payment-service-prd"},
        ]
        assert results[1] == [{"id": "doc-3", "title": "test-project-docs"}]
        assert mock_get.await_count == 2

    async def test_get_single_document(self, linear_client: LinearClient) -> None:
        document = {
            "id": "50e3e770-03ef-4c12-9f5a-e3122a768bc4",
            "title": "payment-service-prd",
            "project": {"id": "project-1", "name": "Surveys"},
        }
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"document": document}}
        mock_post = AsyncMock(return_value=mock_response)

        with patch.object(linear_client.client, "post", mock_post):
            result = await linear_client.get_single_document(
                "50e3e770-03ef-4c12-9f5a-e3122a768bc4"
            )

        assert result == document
        mock_post.assert_awaited_once()
        assert mock_post.await_args is not None
        payload = mock_post.await_args.kwargs["json"]["query"]
        assert "document(id:" in payload.replace(" ", "")
        assert "50e3e770-03ef-4c12-9f5a-e3122a768bc4" in payload
