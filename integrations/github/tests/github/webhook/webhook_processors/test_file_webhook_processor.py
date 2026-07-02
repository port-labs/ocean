from pathlib import Path
from typing import Any

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import (
    GithubFilePattern,
    GithubFileResourceConfig,
    GithubFileSelector,
    RepositoryBranchMapping,
)
from github.webhook.webhook_processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from github.core.options import FileContentOptions


@pytest.fixture
def resource_config() -> GithubFileResourceConfig:
    return GithubFileResourceConfig(
        kind=ObjectKind.FILE,
        selector=GithubFileSelector(
            query="true",
            files=[
                GithubFilePattern(
                    organization="test-org",
                    path="*.yaml",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                    skipParsing=False,
                ),
                GithubFilePattern(
                    organization="test-org",
                    path="*.json",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                    skipParsing=True,
                ),
            ],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".metadata.path",
                    title=".metadata.name",
                    blueprint='"githubFile"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def resource_config_with_items_to_parse() -> GithubFileResourceConfig:
    return GithubFileResourceConfig(
        kind=ObjectKind.FILE,
        selector=GithubFileSelector(
            query="true",
            files=[
                GithubFilePattern(
                    organization="test-org",
                    path="*.yaml",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                    skipParsing=False,
                ),
                GithubFilePattern(
                    organization="test-org",
                    path="*.json",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                    skipParsing=True,
                ),
            ],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".item.name",
                    title=".item.name",
                    blueprint='"githubFile"',
                    properties={},
                )
            ),
            itemsToParse=".content.items",
        ),
    )


@pytest.fixture
def file_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> FileWebhookProcessor:
    return FileWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def payload() -> EventPayload:
    return {
        "ref": "refs/heads/main",
        "before": "abc123",
        "after": "def456",
        "commits": [],
        "repository": {"name": "test-repo", "default_branch": "main"},
        "organization": {"login": "test-org"},
    }


@pytest.mark.asyncio
class TestFileWebhookProcessor:
    async def test_should_process_event_valid_push(
        self, file_webhook_processor: FileWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "push"}
        mock_event.payload = {"ref": "refs/heads/main"}

        assert await file_webhook_processor._should_process_event(mock_event) is True

    async def test_should_process_event_invalid_event_type(
        self, file_webhook_processor: FileWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "issues"}
        mock_event.payload = {"ref": "refs/heads/main"}

        assert await file_webhook_processor._should_process_event(mock_event) is False

    async def test_should_process_event_invalid_ref(
        self, file_webhook_processor: FileWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "push"}
        mock_event.payload = {"ref": "refs/tags/v1.0.0"}

        assert await file_webhook_processor._should_process_event(mock_event) is False

    async def test_get_matching_kinds(
        self, file_webhook_processor: FileWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)

        kinds = await file_webhook_processor.get_matching_kinds(mock_event)
        assert kinds == [ObjectKind.FILE]

    async def test_validate_payload_valid(
        self, file_webhook_processor: FileWebhookProcessor, payload: EventPayload
    ) -> None:
        assert await file_webhook_processor._validate_payload(payload) is True

    async def test_validate_payload_invalid_missing_fields(
        self, file_webhook_processor: FileWebhookProcessor
    ) -> None:
        # Missing 'ref' field
        payload = {
            "before": "abc123",
            "after": "def456",
            "commits": [],
        }
        assert await file_webhook_processor._validate_payload(payload) is False

        # Missing 'before' field
        payload = {
            "ref": "refs/heads/main",
            "after": "def456",
            "commits": [],
        }
        assert await file_webhook_processor._validate_payload(payload) is False

        # Missing 'after' field
        payload = {
            "ref": "refs/heads/main",
            "before": "abc123",
            "commits": [],
        }
        assert await file_webhook_processor._validate_payload(payload) is False

        # Missing 'commits' field
        payload = {
            "ref": "refs/heads/main",
            "before": "abc123",
            "after": "def456",
        }
        assert await file_webhook_processor._validate_payload(payload) is False

    async def test_handle_event_no_matching_patterns(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:

        # Mock the exporter to return no matching files
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {
                    "filename": "README.md",
                    "status": "modified",
                }
            ]
        }

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == []

    async def test_handle_event_no_matching_files(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:

        # Mock the exporter to return no matching files
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {
                    "filename": "README.md",
                    "status": "modified",
                }
            ]
        }

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == []

    async def test_handle_event_with_matching_files(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:

        # Mock file content response
        file_content_response = {
            "content": "name: test\nvalue: 123",
            "name": "config.yaml",
            "path": "config.yaml",
            "size": 20,
        }

        # Mock processed file object
        mock_file_obj = MagicMock()
        mock_file_obj.content = {"name": "test", "value": 123}
        mock_file_obj.repository = {"name": "test-repo"}
        mock_file_obj.branch = "main"
        mock_file_obj.metadata = file_content_response

        # Mock the exporter
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {
                    "filename": "config.yaml",
                    "status": "modified",
                }
            ]
        }
        mock_exporter.get_resource.return_value = file_content_response
        mock_exporter.file_processor.process_file.return_value = mock_file_obj

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 1
            assert result.deleted_raw_results == []

            # Verify exporter calls
            mock_exporter.fetch_commit_diff.assert_called_once_with(
                "test-org", "test-repo", "abc123", "def456"
            )
            requested_refs = {
                call.args[0]["branch"]
                for call in mock_exporter.get_resource.call_args_list
            }
            assert requested_refs == {"main"}
            assert mock_exporter.file_processor.process_file.call_count == 1
            for call in mock_exporter.file_processor.process_file.call_args_list:
                assert call.kwargs["branch"] == "main"

    async def test_handle_event_with_deleted_files(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:

        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {
                    "filename": "config.yaml",
                    "status": "removed",
                }
            ]
        }

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert len(result.deleted_raw_results) == 1
            deleted = result.deleted_raw_results[0]
            assert deleted["metadata"]["path"] == "config.yaml"
            assert deleted["path"] == "config.yaml"
            assert deleted["name"] == "config.yaml"
            assert deleted["branch"] == "main"
            assert "content" not in deleted

            mock_exporter.get_resource.assert_not_called()
            mock_exporter.file_processor.process_file.assert_not_called()

    async def test_handle_event_file_without_content(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:

        # Mock file content response with no content
        file_content_response = {
            "content": None,  # File too large or no content
            "name": "large-file.yaml",
            "path": "large-file.yaml",
            "size": 1024 * 1024 + 1,  # Over 1MB
        }

        # Mock the exporter
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {
                    "filename": "large-file.yaml",
                    "status": "modified",
                }
            ]
        }
        mock_exporter.get_resource.return_value = file_content_response

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == []

    async def test_handle_event_modified_file_carries_old_content_for_deletion(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config_with_items_to_parse: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:
        new_content = "items:\n  - a\n  - b\n"
        old_content = "items:\n  - a\n  - b\n  - c\n"

        def fake_get_resource(options: FileContentOptions) -> dict[str, Any]:
            content = old_content if options["branch"] == "abc123" else new_content
            return {
                "content": content,
                "name": "config.yaml",
                "path": "config.yaml",
                "size": len(content),
            }

        async def fake_process_file(**kwargs: Any) -> dict[str, Any]:
            return {
                "organization": kwargs["organization"],
                "content": kwargs["content"],
                "repository": kwargs["repository"],
                "branch": kwargs["branch"],
                "path": kwargs["file_path"],
                "name": Path(kwargs["file_path"]).name,
                "metadata": kwargs.get("metadata") or {},
            }

        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [{"filename": "config.yaml", "status": "modified"}]
        }
        mock_exporter.get_resource.side_effect = fake_get_resource
        mock_exporter.file_processor.process_file.side_effect = fake_process_file

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(
                payload, resource_config_with_items_to_parse
            )

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 1
            assert len(result.deleted_raw_results) == 1
            assert result.updated_raw_results[0]["content"] == new_content
            assert result.deleted_raw_results[0]["content"] == old_content
            assert result.updated_raw_results[0]["branch"] == "main"
            assert result.deleted_raw_results[0]["branch"] == "main"

            resolve_by_content = {
                call.kwargs["content"]: call.kwargs["should_resolve_references"]
                for call in mock_exporter.file_processor.process_file.call_args_list
            }
            assert resolve_by_content == {new_content: True, old_content: False}

    async def test_handle_event_removed_file_without_old_content_falls_back_to_metadata(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config_with_items_to_parse: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [{"filename": "config.yaml", "status": "removed"}]
        }
        mock_exporter.get_resource.return_value = {
            "content": None,
            "name": "config.yaml",
            "path": "config.yaml",
            "size": 1024 * 1024 + 1,
        }

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(
                payload, resource_config_with_items_to_parse
            )

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert len(result.deleted_raw_results) == 1
            deleted = result.deleted_raw_results[0]
            assert deleted["metadata"]["path"] == "config.yaml"
            assert deleted["name"] == "config.yaml"
            assert "content" not in deleted
            mock_exporter.file_processor.process_file.assert_not_called()

    async def test_handle_event_modified_file_without_old_content_is_not_deleted(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [{"filename": "config.yaml", "status": "modified"}]
        }
        mock_exporter.get_resource.return_value = {
            "content": None,
            "name": "config.yaml",
            "path": "config.yaml",
            "size": 1024 * 1024 + 1,
        }

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == []

    async def test_handle_event_renamed_file_uses_previous_filename_for_old_content(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config_with_items_to_parse: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:
        async def fake_process_file(**kwargs: Any) -> dict[str, Any]:
            return {
                "organization": kwargs["organization"],
                "content": kwargs["content"],
                "repository": kwargs["repository"],
                "branch": kwargs["branch"],
                "path": kwargs["file_path"],
                "name": Path(kwargs["file_path"]).name,
                "metadata": kwargs.get("metadata") or {},
            }

        def fake_get_resource(options: FileContentOptions) -> dict[str, Any]:
            return {
                "content": "name: test",
                "name": Path(options["file_path"]).name,
                "path": options["file_path"],
                "size": 9,
            }

        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {
                    "filename": "new.yaml",
                    "previous_filename": "old.yaml",
                    "status": "renamed",
                }
            ]
        }
        mock_exporter.get_resource.side_effect = fake_get_resource
        mock_exporter.file_processor.process_file.side_effect = fake_process_file

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(
                payload, resource_config_with_items_to_parse
            )

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 1
            assert len(result.deleted_raw_results) == 1
            assert result.updated_raw_results[0]["path"] == "new.yaml"
            assert result.deleted_raw_results[0]["path"] == "old.yaml"

            fetches = {
                (call.args[0]["file_path"], call.args[0]["branch"])
                for call in mock_exporter.get_resource.call_args_list
            }
            assert fetches == {("new.yaml", "main"), ("old.yaml", "abc123")}

    async def test_handle_event_renamed_file_without_items_to_parse_deletes_old_path(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:
        async def fake_process_file(**kwargs: Any) -> dict[str, Any]:
            return {
                "organization": kwargs["organization"],
                "content": kwargs["content"],
                "repository": kwargs["repository"],
                "branch": kwargs["branch"],
                "path": kwargs["file_path"],
                "name": Path(kwargs["file_path"]).name,
                "metadata": kwargs.get("metadata") or {},
            }

        def fake_get_resource(options: FileContentOptions) -> dict[str, Any]:
            return {
                "content": "name: test",
                "name": Path(options["file_path"]).name,
                "path": options["file_path"],
                "size": 9,
            }

        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {
                    "filename": "new.yaml",
                    "previous_filename": "old.yaml",
                    "status": "renamed",
                }
            ]
        }
        mock_exporter.get_resource.side_effect = fake_get_resource
        mock_exporter.file_processor.process_file.side_effect = fake_process_file

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == 1
            assert len(result.deleted_raw_results) == 1
            assert result.updated_raw_results[0]["path"] == "new.yaml"

            deleted = result.deleted_raw_results[0]
            assert deleted["metadata"]["path"] == "old.yaml"
            assert deleted["name"] == "old.yaml"
            assert "content" not in deleted

            fetches = {
                (call.args[0]["file_path"], call.args[0]["branch"])
                for call in mock_exporter.get_resource.call_args_list
            }
            assert fetches == {("new.yaml", "main")}

    async def test_handle_event_processing_error(
        self,
        file_webhook_processor: FileWebhookProcessor,
        resource_config: GithubFileResourceConfig,
        payload: EventPayload,
    ) -> None:

        # Mock file content response
        file_content_response = {
            "content": "name: test\nvalue: 123",
            "name": "config.yaml",
            "path": "config.yaml",
            "size": 20,
        }

        # Mock the exporter to raise an exception during processing
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {
                    "filename": "config.yaml",
                    "status": "modified",
                }
            ]
        }
        mock_exporter.get_resource.return_value = file_content_response
        mock_exporter.file_processor.process_file.side_effect = Exception(
            "Processing error"
        )

        with patch(
            "github.webhook.webhook_processors.file_webhook_processor.RestFileExporter",
            return_value=mock_exporter,
        ):
            result = await file_webhook_processor.handle_event(payload, resource_config)

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == []
