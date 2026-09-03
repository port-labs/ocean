from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linear.client import LinearClient


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
class TestLinearNewResourceClient:
    async def test_get_paginated_users(self, linear_client: LinearClient) -> None:
        from linear.client import LinearObject, PAGE_SIZE

        first_page = {
            "data": {
                "users": {
                    "nodes": [
                        {"id": "user-1", "name": "Alice"},
                        {"id": "user-2", "name": "Bob"},
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": "cursor-1"},
                }
            }
        }

        with patch.object(
            linear_client, "_get_paginated_objects", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = first_page
            results = [batch async for batch in linear_client.get_paginated_users()]

        assert results == [
            [
                {"id": "user-1", "name": "Alice"},
                {"id": "user-2", "name": "Bob"},
            ]
        ]
        mock_get.assert_awaited_once_with(LinearObject.USERS, PAGE_SIZE, None)

    async def test_get_paginated_team_members(
        self, linear_client: LinearClient
    ) -> None:
        from linear.client import LinearObject, PAGE_SIZE

        page = {
            "data": {
                "teamMemberships": {
                    "nodes": [
                        {
                            "id": "membership-1",
                            "owner": True,
                            "team": {"id": "team-1", "key": "ENG"},
                            "user": {"id": "user-1", "name": "Alice"},
                        }
                    ],
                    "pageInfo": {"hasNextPage": False, "endCursor": "cursor-1"},
                }
            }
        }

        with patch.object(
            linear_client, "_get_paginated_objects", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = page
            results = [
                batch async for batch in linear_client.get_paginated_team_members()
            ]

        assert results == [page["data"]["teamMemberships"]["nodes"]]
        mock_get.assert_awaited_once_with(
            LinearObject.TEAM_MEMBERSHIPS, PAGE_SIZE, None
        )
