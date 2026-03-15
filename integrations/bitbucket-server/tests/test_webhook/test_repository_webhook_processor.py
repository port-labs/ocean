from unittest.mock import AsyncMock, MagicMock

import pytest

from webhook_processors.processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)


@pytest.fixture
def repository_webhook_processor() -> RepositoryWebhookProcessor:
    processor = RepositoryWebhookProcessor(event=MagicMock())
    processor._client = MagicMock()
    processor._client.get_single_repository = AsyncMock()
    return processor


@pytest.mark.asyncio
class TestRepositoryWebhookProcessor:
    async def test_repo_modified_emits_deletion_when_slug_changes(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        repository_webhook_processor._client.get_single_repository.return_value = {  # type: ignore[attr-defined]
            "slug": "repo-2",
            "project": {"key": "PROJ"},
        }

        payload = {
            "eventKey": "repo:modified",
            "old": {"slug": "repo-1", "project": {"key": "PROJ"}},
            "new": {"slug": "repo-2", "project": {"key": "PROJ"}},
        }

        result = await repository_webhook_processor.handle_event(payload, MagicMock())

        assert result.updated_raw_results == [
            {"slug": "repo-2", "project": {"key": "PROJ"}}
        ]
        assert result.deleted_raw_results == [
            {"slug": "repo-1", "project": {"key": "PROJ"}}
        ]

    async def test_repo_modified_emits_deletion_when_project_changes(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        repository_webhook_processor._client.get_single_repository.return_value = {  # type: ignore[attr-defined]
            "slug": "repo",
            "project": {"key": "PROJ_B"},
        }

        payload = {
            "eventKey": "repo:modified",
            "old": {"slug": "repo", "project": {"key": "PROJ_A"}},
            "new": {"slug": "repo", "project": {"key": "PROJ_B"}},
        }

        result = await repository_webhook_processor.handle_event(payload, MagicMock())

        assert result.updated_raw_results == [
            {"slug": "repo", "project": {"key": "PROJ_B"}}
        ]
        assert result.deleted_raw_results == [
            {"slug": "repo", "project": {"key": "PROJ_A"}}
        ]

    async def test_repo_modified_does_not_delete_when_identifier_parts_unchanged(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        repository_webhook_processor._client.get_single_repository.return_value = {  # type: ignore[attr-defined]
            "slug": "repo",
            "project": {"key": "PROJ"},
            "name": "New Name",
        }

        payload = {
            "eventKey": "repo:modified",
            "old": {"slug": "repo", "project": {"key": "PROJ"}, "name": "Old Name"},
            "new": {"slug": "repo", "project": {"key": "PROJ"}, "name": "New Name"},
        }

        result = await repository_webhook_processor.handle_event(payload, MagicMock())

        assert result.updated_raw_results == [
            {"slug": "repo", "project": {"key": "PROJ"}, "name": "New Name"}
        ]
        assert result.deleted_raw_results == []

    async def test_repo_refs_changed_never_emits_deletion(
        self, repository_webhook_processor: RepositoryWebhookProcessor
    ) -> None:
        repository_webhook_processor._client.get_single_repository.return_value = {  # type: ignore[attr-defined]
            "slug": "repo",
            "project": {"key": "PROJ"},
        }

        payload = {
            "eventKey": "repo:refs_changed",
            "repository": {"slug": "repo", "project": {"key": "PROJ"}},
        }

        result = await repository_webhook_processor.handle_event(payload, MagicMock())

        assert result.updated_raw_results == [
            {"slug": "repo", "project": {"key": "PROJ"}}
        ]
        assert result.deleted_raw_results == []
