import pytest
from unittest.mock import AsyncMock, MagicMock

from gitlab.webhook.webhook_processors.file_push_webhook_processor import (
    FilePushWebhookProcessor,
)
from gitlab.enrichments.included_files import (
    IncludedFilesEnricher,
    FileIncludedFilesStrategy,
)
from gitlab.helpers.utils import ObjectKind
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from typing import Any


@pytest.mark.asyncio
class TestFilePushWebhookProcessor:
    """Test the file push webhook processor"""

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        """Create a mock webhook event"""
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Push Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> FilePushWebhookProcessor:
        """Create a FilePushWebhookProcessor instance"""
        processor = FilePushWebhookProcessor(event=mock_event)
        # Don't initialize the client here - we'll do it in each test
        return processor

    @pytest.fixture
    def push_payload(self) -> dict[str, Any]:
        """Create a sample push webhook payload"""
        return {
            "object_kind": "push",
            "event_name": "push",
            "before": "abc123",
            "after": "def456",
            "ref": "refs/heads/main",
            "checkout_sha": "def456",
            "user_id": 1,
            "user_name": "Test User",
            "project_id": 68204746,
            "project": {
                "id": 68204746,
                "name": "project7",
                "path_with_namespace": "getport-labs/project7",
                "default_branch": "main",
                "url": "https://gitlab.example.com/getport-labs/project7.git",
                "description": "Test repository",
                "homepage": "https://gitlab.example.com/getport-labs/project7",
            },
            "commits": [
                {
                    "id": "def4567890",
                    "added": ["package.json"],
                    "modified": ["src/data.json", "readme.md"],
                }
            ],
        }

    @staticmethod
    def mock_compare(
        client: MagicMock,
        added: list[str] | None = None,
        deleted: list[str] | None = None,
        modified: list[str] | None = None,
    ) -> None:
        """Stub the repository compare API the processor resolves paths from."""
        diffs: list[dict[str, Any]] = [
            {
                "new_path": path,
                "old_path": path,
                "new_file": True,
                "deleted_file": False,
            }
            for path in added or []
        ]
        diffs.extend(
            {
                "new_path": path,
                "old_path": path,
                "new_file": False,
                "deleted_file": False,
            }
            for path in modified or []
        )
        diffs.extend(
            {"new_path": path, "old_path": path, "deleted_file": True}
            for path in deleted or []
        )
        client.compare_repository = AsyncMock(return_value={"diffs": diffs})

    @pytest.fixture
    def mock_files_selector(self) -> MagicMock:
        """Mock the FilesSelector class with default no-repos config"""
        files_selector = MagicMock()
        files_selector.path = "*.json"
        files_selector.repos = None  # Default case: no repos provided
        files_selector.skip_parsing = False
        return files_selector

    @pytest.fixture
    def mock_gitlab_files_selector(self, mock_files_selector: MagicMock) -> MagicMock:
        """Mock the GitLabFilesSelector class"""
        gitlab_files_selector = MagicMock()
        gitlab_files_selector.files = mock_files_selector
        return gitlab_files_selector

    @pytest.fixture
    def resource_config(self, mock_gitlab_files_selector: MagicMock) -> ResourceConfig:
        """Create a mocked GitLabFilesResourceConfig with default no-repos config"""
        config = MagicMock()
        config.selector = mock_gitlab_files_selector
        config.selector.included_files = []
        config.kind = "file"
        config.port = MagicMock()
        config.port.items_to_parse = None
        return config

    async def test_get_matching_kinds(
        self, processor: FilePushWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        """Test that get_matching_kinds returns the FILE kind"""
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.FILE]

    async def test_skips_non_default_branch(
        self,
        processor: FilePushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test that file push events only process default branch changes"""
        payload = {**push_payload, "ref": "refs/heads/feature"}
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        processor._gitlab_webhook_client.compare_repository.assert_not_called()

    async def test_skips_when_default_branch_unknown(
        self,
        processor: FilePushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test that file push events are skipped when the default branch is missing"""
        project = {**push_payload["project"]}
        project.pop("default_branch")
        payload = {**push_payload, "project": project}
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        processor._gitlab_webhook_client.compare_repository.assert_not_called()

    async def test_processes_default_branch_push(
        self,
        processor: FilePushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test that default branch file push events resolve changed paths."""
        project_id = push_payload["project_id"]
        processor._gitlab_webhook_client = MagicMock()
        self.mock_compare(
            processor._gitlab_webhook_client,
            added=["package.json"],
        )
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=[]
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            return_value=[]
        )

        result = await processor.handle_event(push_payload, resource_config)

        processor._gitlab_webhook_client.compare_repository.assert_awaited_once_with(
            push_payload["project"]["path_with_namespace"],
            push_payload["before"],
            push_payload["after"],
        )
        processor._gitlab_webhook_client._process_file_batch.assert_called_once_with(
            [
                {
                    "project_id": str(project_id),
                    "path": "package.json",
                    "ref": push_payload["after"],
                }
            ],
            context=f"project:{project_id}",
            skip_parsing=False,
        )
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_handle_event_with_no_repos(
        self,
        processor: FilePushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling a push event with *.json path and no repos specified"""
        project_id = push_payload["project_id"]

        # Mock file data returned by _process_file_batch
        file_data = [
            {
                "project_id": str(project_id),
                "path": "package.json",
                "ref": push_payload["after"],
                "content": {"name": "my-app", "version": "1.0.0"},
            },
            {
                "project_id": str(project_id),
                "path": "src/data.json",
                "ref": push_payload["after"],
                "content": {"key": "value"},
            },
        ]

        # Mock enriched data returned by _enrich_files_with_repos
        enriched_data = [
            {"file": file_data[0], "repo": push_payload["project"]},
            {"file": file_data[1], "repo": push_payload["project"]},
        ]

        # Create a fresh MagicMock for the client
        processor._gitlab_webhook_client = MagicMock()
        self.mock_compare(
            processor._gitlab_webhook_client,
            added=["package.json", "src/data.json", "readme.md"],
        )

        # Assign AsyncMock objects with return values to methods
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=file_data
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            return_value=enriched_data
        )

        result = await processor.handle_event(push_payload, resource_config)

        # Verify _enrich_files_with_repos was called with processed batch
        processor._gitlab_webhook_client._enrich_files_with_repos.assert_called_once_with(
            file_data
        )

        # Verify results
        assert len(result.updated_raw_results) == 2
        assert result.updated_raw_results == enriched_data
        assert not result.deleted_raw_results

    async def test_handle_event_with_matching_repo(
        self, processor: FilePushWebhookProcessor, push_payload: dict[str, Any]
    ) -> None:
        """Test handling a push event when repo matches configured repos"""
        # Mock FilesSelector with matching repo
        files_selector = MagicMock()
        files_selector.path = "*.json"
        files_selector.repos = ["getport-labs/project7"]  # Matches payload repo
        files_selector.skip_parsing = False

        # Mock GitLabFilesSelector
        gitlab_files_selector = MagicMock()
        gitlab_files_selector.files = files_selector

        # Mock ResourceConfig
        resource_config = MagicMock()
        resource_config.selector = gitlab_files_selector
        resource_config.selector.included_files = []
        resource_config.kind = "file"
        resource_config.port = MagicMock()
        resource_config.port.items_to_parse = None

        project_id = push_payload["project_id"]

        # Mock file data returned by _process_file_batch
        file_data = [
            {
                "project_id": str(project_id),
                "path": "package.json",
                "ref": push_payload["after"],
                "content": {"name": "my-app", "version": "1.0.0"},
            },
            {
                "project_id": str(project_id),
                "path": "src/data.json",
                "ref": push_payload["after"],
                "content": {"key": "value"},
            },
        ]

        # Mock enriched data returned by _enrich_files_with_repos
        enriched_data = [
            {"file": file_data[0], "repo": push_payload["project"]},
            {"file": file_data[1], "repo": push_payload["project"]},
        ]

        processor._gitlab_webhook_client = MagicMock()
        self.mock_compare(
            processor._gitlab_webhook_client,
            added=["package.json", "src/data.json", "readme.md"],
        )

        # Assign AsyncMock objects with return values to methods
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=file_data
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            return_value=enriched_data
        )

        result = await processor.handle_event(push_payload, resource_config)

        # Verify _process_file_batch was called with correct file batch
        expected_file_batch = [
            {
                "project_id": str(project_id),
                "path": "package.json",
                "ref": push_payload["after"],
            },
            {
                "project_id": str(project_id),
                "path": "src/data.json",
                "ref": push_payload["after"],
            },
        ]
        processor._gitlab_webhook_client._process_file_batch.assert_called_once_with(
            expected_file_batch, context=f"project:{project_id}", skip_parsing=False
        )

        # Verify _enrich_files_with_repos was called with processed batch
        processor._gitlab_webhook_client._enrich_files_with_repos.assert_called_once_with(
            file_data
        )

        # Verify results
        assert len(result.updated_raw_results) == 2
        assert result.updated_raw_results == enriched_data
        assert not result.deleted_raw_results

    async def test_handle_event_with_non_matching_repo(
        self, processor: FilePushWebhookProcessor, push_payload: dict[str, Any]
    ) -> None:
        """Test handling a push event when repo doesn't match configured repos"""
        # Mock FilesSelector with non-matching repo
        files_selector = MagicMock()
        files_selector.path = "*.json"
        files_selector.repos = ["other/repo"]
        files_selector.skip_parsing = False

        # Mock GitLabFilesSelector
        gitlab_files_selector = MagicMock()
        gitlab_files_selector.files = files_selector

        # Mock ResourceConfig
        resource_config = MagicMock()
        resource_config.selector = gitlab_files_selector
        resource_config.selector.included_files = []
        resource_config.kind = "file"
        resource_config.port = MagicMock()
        resource_config.port.items_to_parse = None

        processor._gitlab_webhook_client = MagicMock()

        processor._gitlab_webhook_client._process_file_batch = AsyncMock()
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock()

        result = await processor.handle_event(push_payload, resource_config)

        # Verify no processing happens
        processor._gitlab_webhook_client._process_file_batch.assert_not_called()
        processor._gitlab_webhook_client._enrich_files_with_repos.assert_not_called()
        assert not result.updated_raw_results
        assert not result.deleted_raw_results

    async def test_handle_event_with_deleted_files(
        self,
        processor: FilePushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling a push event with deleted files"""

        push_payload["commits"][0]["added"] = []
        push_payload["commits"][0]["modified"] = []
        push_payload["commits"][0]["removed"] = [
            "old-config.json",
            "deprecated/data.json",
        ]

        project_id = push_payload["project_id"]

        deleted_file_data = [
            {
                "project_id": str(project_id),
                "path": "old-config.json",
                "ref": push_payload["before"],
                "content": {"old": "config"},
            },
            {
                "project_id": str(project_id),
                "path": "deprecated/data.json",
                "ref": push_payload["before"],
                "content": {"deprecated": "data"},
            },
        ]

        enriched_deleted_data = [
            {"file": deleted_file_data[0], "repo": push_payload["project"]},
            {"file": deleted_file_data[1], "repo": push_payload["project"]},
        ]

        processor._gitlab_webhook_client = MagicMock()
        self.mock_compare(
            processor._gitlab_webhook_client,
            deleted=["old-config.json", "deprecated/data.json"],
        )

        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=deleted_file_data
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            return_value=enriched_deleted_data
        )

        result = await processor.handle_event(push_payload, resource_config)

        expected_removed_file_batch = [
            {
                "project_id": str(project_id),
                "path": "deprecated/data.json",
                "ref": push_payload["before"],
            },
            {
                "project_id": str(project_id),
                "path": "old-config.json",
                "ref": push_payload["before"],
            },
        ]
        processor._gitlab_webhook_client._process_file_batch.assert_called_once_with(
            expected_removed_file_batch,
            context=f"project:{project_id}",
            skip_parsing=False,
        )

        # Verify _enrich_files_with_repos was called with processed batch
        processor._gitlab_webhook_client._enrich_files_with_repos.assert_called_once_with(
            deleted_file_data
        )

        # Verify results
        assert len(result.deleted_raw_results) == 2
        assert result.deleted_raw_results == enriched_deleted_data
        assert not result.updated_raw_results

    async def test_handle_event_modified_file_fetches_old_content_for_items_to_parse(
        self,
        processor: FilePushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        """Modified files with itemsToParse emit old content as deletes and new as upserts."""
        resource_config.selector.files.path = "services.yaml"
        resource_config.port.items_to_parse = ".file.content"
        project_id = str(push_payload["project_id"])
        new_file = {
            "project_id": project_id,
            "path": "services.yaml",
            "ref": push_payload["after"],
            "content": [{"name": "keep-me"}],
        }
        old_file = {
            "project_id": project_id,
            "path": "services.yaml",
            "ref": push_payload["before"],
            "content": [{"name": "keep-me"}, {"name": "delete-me"}],
        }
        new_enriched = [{"file": new_file, "repo": push_payload["project"]}]
        old_enriched = [{"file": old_file, "repo": push_payload["project"]}]

        processor._gitlab_webhook_client = MagicMock()
        self.mock_compare(
            processor._gitlab_webhook_client,
            modified=["services.yaml"],
        )

        async def process_batch(
            batch: list[dict[str, Any]], **kwargs: Any
        ) -> list[dict[str, Any]]:
            ref = batch[0]["ref"]
            return [new_file if ref == push_payload["after"] else old_file]

        async def enrich(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return (
                new_enriched
                if batch[0]["ref"] == push_payload["after"]
                else old_enriched
            )

        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            side_effect=process_batch
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            side_effect=enrich
        )

        result = await processor.handle_event(push_payload, resource_config)

        process_calls = (
            processor._gitlab_webhook_client._process_file_batch.await_args_list
        )
        processed_batches = [call.args[0] for call in process_calls]
        assert {
            tuple(item["ref"] for item in batch) for batch in processed_batches
        } == {(push_payload["after"],), (push_payload["before"],)}
        assert result.updated_raw_results == new_enriched
        assert result.deleted_raw_results == old_enriched

    async def test_handle_event_falls_back_to_commits_when_compare_fails(
        self,
        processor: FilePushWebhookProcessor,
        push_payload: dict[str, Any],
        resource_config: ResourceConfig,
    ) -> None:
        """A failing compare degrades to the (capped) commits list in the payload."""
        project_id = push_payload["project_id"]

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.compare_repository = AsyncMock(
            side_effect=RuntimeError("compare unavailable")
        )
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=[]
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            return_value=[]
        )

        await processor.handle_event(push_payload, resource_config)

        processor._gitlab_webhook_client._process_file_batch.assert_called_once_with(
            [
                {
                    "project_id": str(project_id),
                    "path": "package.json",
                    "ref": push_payload["after"],
                },
                {
                    "project_id": str(project_id),
                    "path": "src/data.json",
                    "ref": push_payload["after"],
                },
            ],
            context=f"project:{project_id}",
            skip_parsing=False,
        )


@pytest.mark.asyncio
class TestFileEnrichWithIncludedFiles:
    """Tests for the IncludedFilesEnricher with FileIncludedFilesStrategy"""

    async def test_enrich_file_success(self) -> None:
        """Test successful enrichment with included files."""
        client = MagicMock()
        client.get_file_content = AsyncMock(
            side_effect=["readme content", "owners content"]
        )

        file_entity: dict[str, Any] = {
            "file": {"path": "src/main.py"},
            "repo": {
                "id": 1,
                "path_with_namespace": "group/project",
                "default_branch": "main",
            },
            "branch": "main",
        }

        enricher = IncludedFilesEnricher(
            client=client,
            strategy=FileIncludedFilesStrategy(
                included_files=["README.md", "CODEOWNERS"]
            ),
        )
        result = (await enricher.enrich_batch([file_entity]))[0]

        assert result["__includedFiles"] == {
            "README.md": "readme content",
            "CODEOWNERS": "owners content",
        }
        assert client.get_file_content.call_count == 2
        # File is at src/main.py, so included files should be resolved relative to src/
        client.get_file_content.assert_any_call(
            "group/project", "src/README.md", "main"
        )
        client.get_file_content.assert_any_call(
            "group/project", "src/CODEOWNERS", "main"
        )

    async def test_enrich_file_missing_file(self) -> None:
        """Test enrichment when a file cannot be fetched — stores None."""
        client = MagicMock()
        client.get_file_content = AsyncMock(
            side_effect=["content", Exception("Not found")]
        )

        file_entity: dict[str, Any] = {
            "file": {"path": "src/main.py"},
            "repo": {
                "id": 1,
                "path_with_namespace": "group/project",
                "default_branch": "main",
            },
            "branch": "main",
        }

        enricher = IncludedFilesEnricher(
            client=client,
            strategy=FileIncludedFilesStrategy(
                included_files=["README.md", "MISSING.md"]
            ),
        )
        result = (await enricher.enrich_batch([file_entity]))[0]

        assert result["__includedFiles"] == {
            "README.md": "content",
            "MISSING.md": None,
        }

    async def test_enrich_file_empty_file_list(self) -> None:
        """Test enrichment with empty file list yields empty dict."""
        client = MagicMock()
        client.get_file_content = AsyncMock()

        file_entity: dict[str, Any] = {
            "file": {"path": "src/main.py"},
            "repo": {
                "id": 1,
                "path_with_namespace": "group/project",
                "default_branch": "main",
            },
            "branch": "main",
        }

        enricher = IncludedFilesEnricher(
            client=client,
            strategy=FileIncludedFilesStrategy(included_files=[]),
        )
        result = (await enricher.enrich_batch([file_entity]))[0]

        assert result.get("__includedFiles") == {}
        client.get_file_content.assert_not_called()
