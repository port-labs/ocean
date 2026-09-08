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
    async def test_create_events_webhook_updates_existing_webhook(
        self, linear_client: LinearClient
    ) -> None:
        webhook_check_response = MagicMock()
        webhook_check_response.json.return_value = {
            "data": {
                "webhooks": {
                    "nodes": [
                        {
                            "id": "webhook-1",
                            "url": "https://app.getport.io/integration/webhook",
                        }
                    ]
                }
            }
        }
        webhook_update_response = MagicMock()
        mock_post = AsyncMock(
            side_effect=[webhook_check_response, webhook_update_response]
        )

        with patch.object(linear_client.client, "post", mock_post):
            await linear_client.create_events_webhook("https://app.getport.io")

        assert mock_post.await_count == 2
        assert mock_post.await_args_list[1].kwargs["json"]["query"]
        assert "webhookUpdate" in mock_post.await_args_list[1].kwargs["json"]["query"]
        assert "webhook-1" in mock_post.await_args_list[1].kwargs["json"]["query"]

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


@pytest.mark.asyncio
class TestLinearLabelChildrenPagination:
    async def test_paginates_children_past_inline_window(
        self, linear_client: LinearClient
    ) -> None:
        label_page = {
            "data": {
                "issueLabels": {
                    "edges": [
                        {
                            "node": {
                                "id": "label-1",
                                "name": "group",
                                "children": {
                                    "edges": [
                                        {"node": {"id": f"child-{i}"}}
                                        for i in range(250)
                                    ],
                                    "pageInfo": {
                                        "hasNextPage": True,
                                        "endCursor": "child-cursor-1",
                                    },
                                },
                            }
                        }
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": "label-cursor-1"},
                }
            }
        }
        children_page = {
            "data": {
                "issueLabel": {
                    "children": {
                        "edges": [{"node": {"id": "child-250"}}],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": "child-cursor-2",
                        },
                    }
                }
            }
        }

        mock_post = AsyncMock(
            return_value=MagicMock(json=MagicMock(return_value=children_page))
        )
        with (
            patch.object(
                linear_client, "_get_paginated_objects", new_callable=AsyncMock
            ) as mock_get,
            patch.object(linear_client.client, "post", mock_post),
        ):
            mock_get.return_value = label_page
            results = [batch async for batch in linear_client.get_paginated_labels()]

        assert len(results) == 1
        children = results[0][0]["children"]["edges"]
        assert [edge["node"]["id"] for edge in children][-1] == "child-250"
        assert len(children) == 251
        assert mock_post.await_count == 1
        query = mock_post.await_args.kwargs["json"]["query"]
        assert "issueLabel(id:" in query.replace(" ", "")
        assert 'after: "child-cursor-1"' in query

    async def test_no_extra_calls_when_children_fit_inline_window(
        self, linear_client: LinearClient
    ) -> None:
        label_page = {
            "data": {
                "issueLabels": {
                    "edges": [
                        {
                            "node": {
                                "id": "label-1",
                                "name": "group",
                                "children": {
                                    "edges": [{"node": {"id": "child-0"}}],
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": "child-cursor-1",
                                    },
                                },
                            }
                        }
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": "label-cursor-1"},
                }
            }
        }

        mock_post = AsyncMock()
        with (
            patch.object(
                linear_client, "_get_paginated_objects", new_callable=AsyncMock
            ) as mock_get,
            patch.object(linear_client.client, "post", mock_post),
        ):
            mock_get.return_value = label_page
            results = [batch async for batch in linear_client.get_paginated_labels()]

        assert results[0][0]["children"]["edges"] == [{"node": {"id": "child-0"}}]
        mock_post.assert_not_awaited()

    async def test_get_single_label_follows_child_pagination(
        self, linear_client: LinearClient
    ) -> None:
        single_label = {
            "data": {
                "issueLabel": {
                    "id": "label-1",
                    "name": "group",
                    "children": {
                        "edges": [{"node": {"id": f"child-{i}"}} for i in range(50)],
                        "pageInfo": {"hasNextPage": True, "endCursor": "child-cursor-1"},
                    },
                }
            }
        }
        children_page = {
            "data": {
                "issueLabel": {
                    "children": {
                        "edges": [{"node": {"id": "child-50"}}],
                        "pageInfo": {"hasNextPage": False, "endCursor": "child-cursor-2"},
                    }
                }
            }
        }

        mock_post = AsyncMock(
            side_effect=[
                MagicMock(json=MagicMock(return_value=single_label)),
                MagicMock(json=MagicMock(return_value=children_page)),
            ]
        )
        with patch.object(linear_client.client, "post", mock_post):
            label = await linear_client.get_single_label("label-1")

        assert label["id"] == "label-1"
        children = label["children"]["edges"]
        assert len(children) == 51
        assert [edge["node"]["id"] for edge in children][-1] == "child-50"
        query = mock_post.await_args.kwargs["json"]["query"]
        assert 'after: "child-cursor-1"' in query
