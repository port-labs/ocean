from typing import Any
from unittest.mock import MagicMock

import pytest

from helpers.workspace_enricher import (
    enrich_workspaces_with_tags,
    enrich_workspace_with_tags,
)


@pytest.fixture
def mock_terraform_client() -> MagicMock:
    return MagicMock()


class TestEnrichWorkspacesWithTags:
    @pytest.mark.asyncio
    async def test_enrich_workspaces_with_tags_success(
        self, mock_terraform_client: Any
    ) -> None:
        workspaces = [
            {"id": "ws-1", "attributes": {"name": "workspace-1"}},
            {"id": "ws-2", "attributes": {"name": "workspace-2"}},
        ]
        tags_batches = [[{"id": "tag-1"}], [{"id": "tag-2"}]]

        async def mock_get_tags(workspace_id: str) -> Any:
            if workspace_id == "ws-1":
                yield tags_batches[0]
            else:
                yield tags_batches[1]

        mock_terraform_client.get_workspace_tags = mock_get_tags

        result = await enrich_workspaces_with_tags(mock_terraform_client, workspaces)

        assert len(result) == 2
        assert result[0]["__tags"] == [{"id": "tag-1"}]
        assert result[1]["__tags"] == [{"id": "tag-2"}]

    @pytest.mark.asyncio
    async def test_enrich_workspaces_with_tags_empty_list(
        self, mock_terraform_client: Any
    ) -> None:
        result = await enrich_workspaces_with_tags(mock_terraform_client, [])

        assert result == []

    @pytest.mark.asyncio
    async def test_enrich_workspaces_with_tags_api_failure(
        self, mock_terraform_client: Any
    ) -> None:
        workspaces = [
            {"id": "ws-1", "attributes": {"name": "workspace-1"}},
            {"id": "ws-2", "attributes": {"name": "workspace-2"}},
        ]

        async def mock_get_tags(workspace_id: str) -> Any:
            if workspace_id == "ws-1":
                yield [{"id": "tag-1"}]
            else:
                raise Exception("API Error")

        mock_terraform_client.get_workspace_tags = mock_get_tags

        result = await enrich_workspaces_with_tags(mock_terraform_client, workspaces)

        assert len(result) == 2
        assert result[0]["__tags"] == [{"id": "tag-1"}]
        assert result[1]["__tags"] == []

    @pytest.mark.asyncio
    async def test_enrich_workspaces_with_multiple_tag_batches(
        self, mock_terraform_client: Any
    ) -> None:
        workspaces = [{"id": "ws-1", "attributes": {"name": "workspace-1"}}]

        async def mock_get_tags(workspace_id: str) -> Any:
            yield [{"id": "tag-1"}]
            yield [{"id": "tag-2"}]
            yield [{"id": "tag-3"}]

        mock_terraform_client.get_workspace_tags = mock_get_tags

        result = await enrich_workspaces_with_tags(mock_terraform_client, workspaces)

        assert len(result) == 1
        assert len(result[0]["__tags"]) == 3
        assert result[0]["__tags"] == [
            {"id": "tag-1"},
            {"id": "tag-2"},
            {"id": "tag-3"},
        ]


class TestEnrichWorkspaceWithTags:
    @pytest.mark.asyncio
    async def test_enrich_workspace_with_tags_success(
        self, mock_terraform_client: Any
    ) -> None:
        workspace = {"id": "ws-1", "attributes": {"name": "workspace-1"}}

        async def mock_get_tags(workspace_id: str) -> Any:
            yield [{"id": "tag-1"}, {"id": "tag-2"}]

        mock_terraform_client.get_workspace_tags = mock_get_tags

        result = await enrich_workspace_with_tags(mock_terraform_client, workspace)

        assert result["id"] == "ws-1"
        assert len(result["__tags"]) == 2
        assert result["__tags"] == [{"id": "tag-1"}, {"id": "tag-2"}]

    @pytest.mark.asyncio
    async def test_enrich_workspace_with_tags_no_tags(
        self, mock_terraform_client: Any
    ) -> None:
        workspace = {"id": "ws-1", "attributes": {"name": "workspace-1"}}

        async def mock_get_tags(workspace_id: str) -> Any:
            yield []

        mock_terraform_client.get_workspace_tags = mock_get_tags

        result = await enrich_workspace_with_tags(mock_terraform_client, workspace)

        assert result["__tags"] == []

    @pytest.mark.asyncio
    async def test_enrich_workspace_with_tags_api_failure(
        self, mock_terraform_client: Any
    ) -> None:
        workspace = {"id": "ws-1", "attributes": {"name": "workspace-1"}}

        async def mock_get_tags(workspace_id: str) -> Any:
            if False:
                yield []
            raise Exception("API Error")

        mock_terraform_client.get_workspace_tags = mock_get_tags

        result = await enrich_workspace_with_tags(mock_terraform_client, workspace)

        assert result["__tags"] == []

    @pytest.mark.asyncio
    async def test_enrich_workspace_preserves_original_data(
        self, mock_terraform_client: Any
    ) -> None:
        workspace = {
            "id": "ws-1",
            "attributes": {"name": "workspace-1", "locked": False},
            "relationships": {"organization": {"data": {"id": "org-1"}}},
        }

        async def mock_get_tags(workspace_id: str) -> Any:
            yield [{"id": "tag-1"}]

        mock_terraform_client.get_workspace_tags = mock_get_tags

        result = await enrich_workspace_with_tags(mock_terraform_client, workspace)

        assert result["id"] == "ws-1"
        assert result["attributes"]["name"] == "workspace-1"
        assert result["attributes"]["locked"] is False
        assert result["relationships"]["organization"]["data"]["id"] == "org-1"
        assert result["__tags"] == [{"id": "tag-1"}]

