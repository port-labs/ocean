import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, Dict, List, Set, Tuple

from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
    EventPayload,
)
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.workflow_webhook_processor import (
    WorkflowWebhookProcessor,
)
from github.core.exporters.workflows_exporter import RestWorkflowExporter
from github.core.options import SingleWorkflowOptions


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.WORKFLOW,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"githubWorkflow"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def workflow_webhook_processor() -> WorkflowWebhookProcessor:
    # We don't need a specific event for instantiation, as methods take event as an argument
    return WorkflowWebhookProcessor(event=MagicMock())


class TestWorkflowWebhookProcessor:
    @pytest.mark.parametrize(
        "github_event, commits_payload, expected_result",
        [
            # Push event with added workflow file
            (
                "push",
                [
                    {
                        "modified": [],
                        "added": [".github/workflows/test.yml"],
                        "removed": [],
                    }
                ],
                True,
            ),
            # Push event with modified workflow file
            (
                "push",
                [
                    {
                        "modified": [".github/workflows/another.yml"],
                        "added": [],
                        "removed": [],
                    }
                ],
                True,
            ),
            # Push event with removed workflow file
            (
                "push",
                [
                    {
                        "modified": [],
                        "added": [],
                        "removed": [".github/workflows/deleted.yml"],
                    }
                ],
                True,
            ),
            # Push event with non-workflow file changes
            (
                "push",
                [{"modified": ["other_file.txt"], "added": [], "removed": []}],
                False,
            ),
            # Push event with no changes
            ("push", [{"modified": [], "added": [], "removed": []}], False),
            # Non-push event with workflow file changes
            (
                "pull_request",
                [
                    {
                        "modified": [],
                        "added": [".github/workflows/test.yml"],
                        "removed": [],
                    }
                ],
                False,
            ),
            # Multiple commits, one with workflow change
            (
                "push",
                [
                    {"modified": ["file1.txt"]},
                    {"added": [".github/workflows/multi_commit.yml"]},
                ],
                True,
            ),
            # Multiple commits, none with workflow change
            ("push", [{"modified": ["file1.txt"]}, {"added": ["file2.txt"]}], False),
            # Empty commits list
            ("push", [], False),
        ],
    )
    async def test_should_process_event(
        self,
        workflow_webhook_processor: WorkflowWebhookProcessor,
        github_event: str,
        commits_payload: List[Dict[str, Any]] | None,
        expected_result: bool,
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"commits": commits_payload} if commits_payload is not None else {},
            headers={"x-github-event": github_event},
        )
        assert (
            await workflow_webhook_processor._should_process_event(event)
            is expected_result
        )

    async def test_get_matching_kinds(
        self, workflow_webhook_processor: WorkflowWebhookProcessor
    ) -> None:
        event = WebhookEvent(trace_id="test", payload={}, headers={})
        kinds = await workflow_webhook_processor.get_matching_kinds(event)
        assert ObjectKind.WORKFLOW in kinds
        assert len(kinds) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mock_commit_diff_files, mock_extracted_updated_workflows, mock_extracted_deleted_workflows, mock_exporter_workflow_data, expected_updated_count, expected_deleted_count",
        [
            # Case 1: Workflow added/modified
            (
                [{"filename": ".github/workflows/test.yml", "status": "added"}],
                [{"filename": ".github/workflows/test.yml"}],
                [],
                {"id": "test_workflow", "name": "Test Workflow"},
                1,
                0,
            ),
            # Case 2: Workflow deleted
            (
                [{"filename": ".github/workflows/deleted.yml", "status": "removed"}],
                [],
                [{"filename": ".github/workflows/deleted.2.yml"}],
                None,
                0,
                1,
            ),
            # Case 3: Both updated and deleted
            (
                [
                    {"filename": ".github/workflows/updated.yml", "status": "modified"},
                    {"filename": ".github/workflows/removed.yml", "status": "removed"},
                ],
                [{"filename": ".github/workflows/updated.yml"}],
                [{"filename": ".github/workflows/removed.yml"}],
                {"id": "updated_workflow", "name": "Updated Workflow"},
                1,
                1,
            ),
            # Case 4: No relevant workflow changes
            ([{"filename": "some_file.txt", "status": "modified"}], [], [], None, 0, 0),
            # Case 5: Multiple workflows updated
            (
                [
                    {"filename": ".github/workflows/wf1.yml", "status": "modified"},
                    {"filename": ".github/workflows/wf2.yml", "status": "added"},
                ],
                [
                    {"filename": ".github/workflows/wf1.yml"},
                    {"filename": ".github/workflows/wf2.yml"},
                ],
                [],
                {"id": "workflow_base", "name": "Workflow Base"},
                2,
                0,
            ),
        ],
    )
    async def test_handle_event(
        self,
        workflow_webhook_processor: WorkflowWebhookProcessor,
        resource_config: ResourceConfig,
        mock_commit_diff_files: List[Dict[str, Any]],
        mock_extracted_updated_workflows: List[Dict[str, Any]],
        mock_extracted_deleted_workflows: List[Dict[str, Any]],
        mock_exporter_workflow_data: Dict[str, Any] | None,
        expected_updated_count: int,
        expected_deleted_count: int,
    ) -> None:
        payload: EventPayload = {
            "repository": {"name": "test-repo"},
            "before": "sha1",
            "after": "sha2",
            "commits": [{}],  # Minimal for _validate_payload
            "ref": "refs/heads/main",  # Minimal for _validate_payload
        }

        mock_rest_client = MagicMock()
        mock_rest_client.send_api_request.return_value = AsyncMock()
        mock_exporter = AsyncMock(spec=RestWorkflowExporter)

        if expected_updated_count > 0:
            # Use side_effect to return different data for each call if multiple updates are expected
            mock_exporter.get_resource.side_effect = [
                {
                    **mock_exporter_workflow_data,
                    "id": f"{mock_exporter_workflow_data['id']}_{i}",
                }
                for i in range(expected_updated_count)
            ]
        else:
            mock_exporter.get_resource.return_value = None

        with (
            patch(
                "github.clients.client_factory.create_github_client",
                return_value=mock_rest_client,
            ),
            patch(
                "github.helpers.utils.fetch_commit_diff",
                return_value={"files": mock_commit_diff_files},
            ),
            patch(
                "github.helpers.utils.extract_changed_files",
                return_value=(
                    set(x["filename"] for x in mock_extracted_updated_workflows),
                    set(x["filename"] for x in mock_extracted_deleted_workflows),
                ),
            ),
        ):
            result = await workflow_webhook_processor.handle_event(
                payload, resource_config
            )

            assert isinstance(result, WebhookEventRawResults)
            assert len(result.updated_raw_results) == expected_updated_count
            assert len(result.deleted_raw_results) == expected_deleted_count

            if expected_updated_count > 0:
                assert mock_exporter.get_resource.call_count == expected_updated_count
                # Verify arguments for each call
                for i, workflow_file in enumerate(mock_extracted_updated_workflows):
                    expected_options = SingleWorkflowOptions(
                        repo_name="test-repo", workflow_id=workflow_file["filename"]
                    )
                    # Check if the call arguments match the expected options
                    mock_exporter.get_resource.assert_any_call(expected_options)
            else:
                mock_exporter.get_resource.assert_not_called()

            if expected_deleted_count > 0:
                deleted_filenames = {
                    item["path"] for item in result.deleted_raw_results
                }
                expected_deleted_filenames = {
                    f["filename"] for f in mock_extracted_deleted_workflows
                }
                assert deleted_filenames == expected_deleted_filenames

    @pytest.mark.parametrize(
        "payload, expected_result",
        [
            ({"commits": [{}], "ref": "refs/heads/main"}, True),  # Valid
            ({"commits": [{}], "ref": "refs/tags/v1.0"}, False),  # Invalid ref
            ({"ref": "refs/heads/main"}, False),  # Missing commits
            ({"commits": [{}]}, False),  # Missing ref
            ({}, False),  # Empty payload
        ],
    )
    async def test_validate_payload(
        self,
        workflow_webhook_processor: WorkflowWebhookProcessor,
        payload: EventPayload,
        expected_result: bool,
    ) -> None:
        assert (
            await workflow_webhook_processor._validate_payload(payload)
            is expected_result
        )

    @pytest.mark.parametrize(
        "file_path, expected_result",
        [
            (".github/workflows/main.yml", True),
            (".github/workflows/test_workflow.yaml", True),
            ("workflows/main.yml", False),  # Wrong directory
            (".github/workflows/main.txt", False),  # Wrong extension
            (
                ".github/workflows/sub_dir/main.yml",
                True,
            ),  # Subdirectory is still a workflow file
            ("README.md", False),
            (
                "",
                False,
            ),
        ],
    )
    def test_is_workflow_file(
        self,
        workflow_webhook_processor: WorkflowWebhookProcessor,
        file_path: str,
        expected_result: bool,
    ) -> None:
        assert (
            workflow_webhook_processor._is_workflow_file(file_path) is expected_result
        )
