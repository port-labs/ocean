from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

from linear.client import LinearClient
from linear.core.exporters import DocumentExporter
from linear.core.exporters.document_exporter import GetDocumentOptions
from linear.core.exporters.label_exporter import GetLabelOptions, LabelExporter
from linear.core.exceptions import LinearApiError
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
        mock_execute_query_template = AsyncMock(
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

        with patch.object(
            linear_client.graphql,
            "execute_query_template",
            mock_execute_query_template,
        ):
            await webhook_client.create_events_webhook("https://app.getport.io")

        assert mock_execute_query_template.await_count == 2
        assert (
            mock_execute_query_template.await_args_list[1].args[0]
            == "UPDATE_LIVE_EVENTS_WEBHOOK"
        )
        assert (
            mock_execute_query_template.await_args_list[1].kwargs["webhook_id"]
            == "webhook-1"
        )


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
            results = [batch async for batch in exporter.get_paginated_resources()]

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


@pytest.mark.asyncio
class TestLinearLabelChildrenPagination:
    async def test_follows_multiple_children_pages(
        self, linear_client: LinearClient
    ) -> None:
        label = {
            "id": "label-1",
            "children": {
                "edges": [{"node": {"id": "child-1"}}],
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
            },
        }
        mock_execute = AsyncMock(
            side_effect=[
                {"issueLabel": label},
                {
                    "issueLabel": {
                        "children": {
                            "edges": [{"node": {"id": "child-2"}}],
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor-2"},
                        }
                    }
                },
                {
                    "issueLabel": {
                        "children": {
                            "edges": [{"node": {"id": "child-3"}}],
                            "pageInfo": {"hasNextPage": False, "endCursor": "cursor-3"},
                        }
                    }
                },
            ]
        )
        with patch.object(linear_client.graphql, "execute", mock_execute):
            result = await LabelExporter(linear_client).get_resource(
                GetLabelOptions(resource_id="label-1")
            )
        assert [edge["node"]["id"] for edge in result["children"]["edges"]] == [
            "child-1",
            "child-2",
            "child-3",
        ]
        assert 'after: "cursor-1"' in mock_execute.await_args_list[1].args[0]
        assert 'after: "cursor-2"' in mock_execute.await_args_list[2].args[0]

    @pytest.mark.parametrize("cursor", [None, "cursor-1"])
    async def test_rejects_nonadvancing_children_page(
        self, linear_client: LinearClient, cursor: str | None
    ) -> None:
        label = {
            "id": "label-1",
            "children": {
                "edges": [],
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
            },
        }
        mock_execute = AsyncMock(
            side_effect=[
                {"issueLabel": label},
                {
                    "issueLabel": {
                        "children": {
                            "edges": [],
                            "pageInfo": {"hasNextPage": True, "endCursor": cursor},
                        }
                    }
                },
            ]
        )
        with patch.object(linear_client.graphql, "execute", mock_execute):
            with pytest.raises(LinearApiError, match="pagination did not advance"):
                await LabelExporter(linear_client).get_resource(
                    GetLabelOptions(resource_id="label-1")
                )
        assert mock_execute.await_count == 2

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
                                        for i in range(50)
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
                        "edges": [{"node": {"id": "child-50"}}],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": "child-cursor-2",
                        },
                    }
                }
            }
        }

        exporter = LabelExporter(linear_client)
        mock_execute = AsyncMock(
            side_effect=[label_page["data"], children_page["data"]]
        )
        with patch.object(linear_client.graphql, "execute", mock_execute):
            results = [batch async for batch in exporter.get_paginated_resources()]

        assert len(results) == 1
        children = results[0][0]["children"]["edges"]
        assert [edge["node"]["id"] for edge in children][-1] == "child-50"
        assert len(children) == 51
        assert mock_execute.await_count == 2
        assert mock_execute.await_args is not None
        query = mock_execute.await_args.args[0]
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

        exporter = LabelExporter(linear_client)
        mock_execute = AsyncMock(return_value=label_page["data"])
        with patch.object(linear_client.graphql, "execute", mock_execute):
            results = [batch async for batch in exporter.get_paginated_resources()]

        assert results[0][0]["children"]["edges"] == [{"node": {"id": "child-0"}}]
        mock_execute.assert_awaited_once()

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
                        "pageInfo": {
                            "hasNextPage": True,
                            "endCursor": "child-cursor-1",
                        },
                    },
                }
            }
        }
        children_page = {
            "data": {
                "issueLabel": {
                    "children": {
                        "edges": [{"node": {"id": "child-50"}}],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": "child-cursor-2",
                        },
                    }
                }
            }
        }

        exporter = LabelExporter(linear_client)
        mock_execute = AsyncMock(
            side_effect=[single_label["data"], children_page["data"]]
        )
        with patch.object(linear_client.graphql, "execute", mock_execute):
            label = await exporter.get_resource(GetLabelOptions(resource_id="label-1"))

        assert label["id"] == "label-1"
        children = label["children"]["edges"]
        assert len(children) == 51
        assert [edge["node"]["id"] for edge in children][-1] == "child-50"
        assert mock_execute.await_count == 2
        assert mock_execute.await_args is not None
        query = mock_execute.await_args.args[0]
        assert 'after: "child-cursor-1"' in query
