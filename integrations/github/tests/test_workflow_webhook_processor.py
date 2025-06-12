import pytest
from typing import Dict, List, Set, Any
from unittest.mock import AsyncMock, MagicMock

from github.webhook.webhook_processors.workflow_webhook_processor import (
    WorkflowWebhookProcessor,
)


class TestWorkflowWebhookProcessor:
    """Test cases for WorkflowWebhookProcessor."""

    @pytest.fixture
    def processor(self) -> WorkflowWebhookProcessor:
        """Create a WorkflowWebhookProcessor instance for testing."""
        return WorkflowWebhookProcessor()

    def test_is_workflow_file_yml(self, processor: WorkflowWebhookProcessor) -> None:
        """Test detection of .yml workflow files."""
        assert processor._is_workflow_file(".github/workflows/ci.yml") is True

    def test_is_workflow_file_yaml(self, processor: WorkflowWebhookProcessor) -> None:
        """Test detection of .yaml workflow files."""
        assert processor._is_workflow_file(".github/workflows/deploy.yaml") is True

    def test_is_not_workflow_file_wrong_extension(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test that non-yaml files are not detected as workflow files."""
        assert processor._is_workflow_file(".github/workflows/config.json") is False

    def test_is_not_workflow_file_wrong_directory(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test that yaml files outside workflows directory are not detected."""
        assert processor._is_workflow_file(".github/config.yml") is False
        assert processor._is_workflow_file("src/config.yml") is False

    def test_extract_changed_workflow_files_added(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test extraction of added workflow files."""
        payload: Dict[str, List[Dict[str, List[str]]]] = {
            "commits": [
                {
                    "added": [".github/workflows/new-workflow.yml", "src/main.py"],
                    "modified": [],
                    "removed": [],
                }
            ]
        }

        changed_files: Set[str] = processor._extract_changed_workflow_files(payload)
        assert changed_files == {".github/workflows/new-workflow.yml"}

    def test_extract_changed_workflow_files_modified(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test extraction of modified workflow files."""
        payload: Dict[str, List[Dict[str, List[str]]]] = {
            "commits": [
                {
                    "added": [],
                    "modified": [".github/workflows/ci.yml", "README.md"],
                    "removed": [],
                }
            ]
        }

        changed_files: Set[str] = processor._extract_changed_workflow_files(payload)
        assert changed_files == {".github/workflows/ci.yml"}

    def test_extract_changed_workflow_files_removed(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test extraction of removed workflow files."""
        payload: Dict[str, List[Dict[str, List[str]]]] = {
            "commits": [
                {
                    "added": [],
                    "modified": [],
                    "removed": [".github/workflows/old-workflow.yaml", "old-file.txt"],
                }
            ]
        }

        changed_files: Set[str] = processor._extract_changed_workflow_files(payload)
        assert changed_files == {".github/workflows/old-workflow.yaml"}

    def test_extract_changed_workflow_files_multiple_commits(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test extraction across multiple commits."""
        payload: Dict[str, List[Dict[str, List[str]]]] = {
            "commits": [
                {
                    "added": [".github/workflows/workflow1.yml"],
                    "modified": [],
                    "removed": [],
                },
                {
                    "added": [],
                    "modified": [".github/workflows/workflow2.yaml"],
                    "removed": [".github/workflows/old-workflow.yml"],
                },
            ]
        }

        changed_files: Set[str] = processor._extract_changed_workflow_files(payload)
        expected: Set[str] = {
            ".github/workflows/workflow1.yml",
            ".github/workflows/workflow2.yaml",
            ".github/workflows/old-workflow.yml",
        }
        assert changed_files == expected

    def test_extract_changed_workflow_files_no_workflows(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test extraction when no workflow files are changed."""
        payload: Dict[str, List[Dict[str, List[str]]]] = {
            "commits": [
                {
                    "added": ["src/main.py"],
                    "modified": ["README.md"],
                    "removed": ["old-file.txt"],
                }
            ]
        }

        changed_files: Set[str] = processor._extract_changed_workflow_files(payload)
        assert changed_files == set()

    def test_extract_changed_workflow_files_empty_commits(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test extraction with empty commits array."""
        payload: Dict[str, List[Any]] = {"commits": []}

        changed_files: Set[str] = processor._extract_changed_workflow_files(payload)
        assert changed_files == set()

    @pytest.mark.asyncio
    async def test_should_process_event_push_with_workflows(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test that push events with workflow changes are processed."""
        event = MagicMock()
        event.headers = {"x-github-event": "push"}
        event.payload = {
            "commits": [
                {
                    "added": [".github/workflows/ci.yml"],
                    "modified": [],
                    "removed": [],
                }
            ]
        }

        should_process: bool = await processor._should_process_event(event)
        assert should_process is True

    @pytest.mark.asyncio
    async def test_should_process_event_push_without_workflows(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test that push events without workflow changes are not processed."""
        event = MagicMock()
        event.headers = {"x-github-event": "push"}
        event.payload = {
            "commits": [
                {
                    "added": ["src/main.py"],
                    "modified": ["README.md"],
                    "removed": [],
                }
            ]
        }

        should_process: bool = await processor._should_process_event(event)
        assert should_process is False

    @pytest.mark.asyncio
    async def test_should_process_event_non_push(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test that non-push events are not processed."""
        event = MagicMock()
        event.headers = {"x-github-event": "pull_request"}
        event.payload = {}

        should_process: bool = await processor._should_process_event(event)
        assert should_process is False

    @pytest.mark.asyncio
    async def test_validate_payload_valid(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test payload validation with valid push payload."""
        payload: Dict[str, Any] = {
            "commits": [{"added": [], "modified": [], "removed": []}],
            "ref": "refs/heads/main",
        }

        is_valid: bool = await processor._validate_payload(payload)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_payload_missing_commits(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test payload validation with missing commits."""
        payload: Dict[str, str] = {"ref": "refs/heads/main"}

        is_valid: bool = await processor._validate_payload(payload)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_payload_invalid_ref(
        self, processor: WorkflowWebhookProcessor
    ) -> None:
        """Test payload validation with invalid ref (not a branch)."""
        payload: Dict[str, Any] = {
            "commits": [{"added": [], "modified": [], "removed": []}],
            "ref": "refs/tags/v1.0.0",
        }

        is_valid: bool = await processor._validate_payload(payload)
        assert is_valid is False
