import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.branch_webhook_processor import (
    BranchWebhookProcessor,
    DELETED_COMMIT_SHA,
)
from gitlab.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from typing import Any


def make_resource_config(
    default_branch_only: bool = True,
    regex: str | None = None,
    search: str | None = None,
) -> MagicMock:
    config = MagicMock()
    config.selector.default_branch_only = default_branch_only
    config.selector.regex = regex
    config.selector.search = search
    return config


@pytest.mark.asyncio
class TestBranchWebhookProcessor:
    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "push"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> BranchWebhookProcessor:
        return BranchWebhookProcessor(event=mock_event)

    @pytest.fixture
    def base_payload(self) -> dict[str, Any]:
        return {
            "object_kind": "push",
            "ref": "refs/heads/main",
            "after": "abc123def456",
            "project": {
                "id": 42,
                "path_with_namespace": "group/project",
                "default_branch": "main",
            },
        }

    async def test_get_matching_kinds(
        self, processor: BranchWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.BRANCH]

    # --- non-branch ref guard ---

    async def test_non_branch_ref_is_ignored(
        self, processor: BranchWebhookProcessor, base_payload: dict[str, Any]
    ) -> None:
        payload = {**base_payload, "ref": "refs/notes/commits"}
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(payload, make_resource_config())

        processor._gitlab_webhook_client.get_single_branch.assert_not_called()
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    # --- happy path ---

    async def test_handle_event_returns_branch(
        self, processor: BranchWebhookProcessor, base_payload: dict[str, Any]
    ) -> None:
        branch_data = {
            "name": "main",
            "__project": {"path_with_namespace": "group/project"},
        }
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_single_branch = AsyncMock(
            return_value=branch_data
        )

        result = await processor.handle_event(base_payload, make_resource_config())

        processor._gitlab_webhook_client.get_single_branch.assert_called_once()
        assert result.updated_raw_results == [branch_data]
        assert result.deleted_raw_results == []

    async def test_handle_delete_event(
        self, processor: BranchWebhookProcessor, base_payload: dict[str, Any]
    ) -> None:
        payload = {**base_payload, "after": DELETED_COMMIT_SHA}
        enriched = {
            "name": "main",
            "__project": {"path_with_namespace": "group/project"},
        }
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.enrich_with_project_path = MagicMock(
            return_value=enriched
        )

        result = await processor.handle_event(payload, make_resource_config())

        processor._gitlab_webhook_client.enrich_with_project_path.assert_called_once_with(
            {"name": "main"}, "group/project"
        )
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == [enriched]

    # --- fix: selector filters apply to delete events too ---

    async def test_delete_skipped_when_default_branch_only_and_non_default(
        self, processor: BranchWebhookProcessor, base_payload: dict[str, Any]
    ) -> None:
        payload = {
            **base_payload,
            "ref": "refs/heads/feature/foo",
            "after": DELETED_COMMIT_SHA,
        }
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(
            payload, make_resource_config(default_branch_only=True)
        )

        processor._gitlab_webhook_client.enrich_with_project_path.assert_not_called()
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_delete_skipped_when_regex_does_not_match(
        self, processor: BranchWebhookProcessor, base_payload: dict[str, Any]
    ) -> None:
        payload = {
            **base_payload,
            "ref": "refs/heads/feature/foo",
            "after": DELETED_COMMIT_SHA,
        }
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(
            payload,
            make_resource_config(default_branch_only=False, regex=r"release/.*"),
        )

        processor._gitlab_webhook_client.enrich_with_project_path.assert_not_called()
        assert result.deleted_raw_results == []

    async def test_delete_skipped_when_search_does_not_match(
        self, processor: BranchWebhookProcessor, base_payload: dict[str, Any]
    ) -> None:
        payload = {
            **base_payload,
            "ref": "refs/heads/feature/foo",
            "after": DELETED_COMMIT_SHA,
        }
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(
            payload, make_resource_config(default_branch_only=False, search="release")
        )

        processor._gitlab_webhook_client.enrich_with_project_path.assert_not_called()
        assert result.deleted_raw_results == []

    # --- fix: regex and search are mutually exclusive ---

    async def test_regex_takes_precedence_over_search(
        self, processor: BranchWebhookProcessor, base_payload: dict[str, Any]
    ) -> None:
        """When regex matches, search is not evaluated — even if search would reject the branch."""
        payload = {**base_payload, "ref": "refs/heads/release/1.0"}
        branch_data = {"name": "release/1.0"}
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_single_branch = AsyncMock(
            return_value=branch_data
        )

        # regex matches "release/1.0", search does NOT contain "feature" — search should be ignored
        result = await processor.handle_event(
            payload,
            make_resource_config(
                default_branch_only=False, regex=r"release/.*", search="feature"
            ),
        )

        assert result.updated_raw_results == [branch_data]
        assert result.deleted_raw_results == []

    async def test_search_not_evaluated_when_regex_rejects(
        self, processor: BranchWebhookProcessor, base_payload: dict[str, Any]
    ) -> None:
        """When regex rejects the branch, search is not evaluated — the branch is skipped."""
        payload = {**base_payload, "ref": "refs/heads/feature/foo"}
        processor._gitlab_webhook_client = MagicMock()

        # regex does not match; search would match — search should be ignored
        result = await processor.handle_event(
            payload,
            make_resource_config(
                default_branch_only=False, regex=r"release/.*", search="feature"
            ),
        )

        processor._gitlab_webhook_client.get_single_branch.assert_not_called()
        assert result.updated_raw_results == []

    # --- fix: search is a substring check only ---

    async def test_search_matches_substring_not_at_start(
        self, processor: BranchWebhookProcessor, base_payload: dict[str, Any]
    ) -> None:
        """A branch containing the search term in the middle should not be skipped."""
        payload = {**base_payload, "ref": "refs/heads/feature/api-update"}
        branch_data = {"name": "feature/api-update"}
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_single_branch = AsyncMock(
            return_value=branch_data
        )

        result = await processor.handle_event(
            payload,
            make_resource_config(default_branch_only=False, search="api"),
        )

        processor._gitlab_webhook_client.get_single_branch.assert_called_once()
        assert result.updated_raw_results == [branch_data]

    async def test_search_skips_branch_when_term_absent(
        self, processor: BranchWebhookProcessor, base_payload: dict[str, Any]
    ) -> None:
        payload = {**base_payload, "ref": "refs/heads/feature/foo"}
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(
            payload,
            make_resource_config(default_branch_only=False, search="release"),
        )

        processor._gitlab_webhook_client.get_single_branch.assert_not_called()
        assert result.updated_raw_results == []
