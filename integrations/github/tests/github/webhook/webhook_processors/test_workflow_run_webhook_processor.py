from typing import Dict
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.events import WORKFLOW_UPSERT_EVENTS


from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.workflow_run.workflow_run_webhook_processor import (
    WorkflowRunWebhookProcessor,
)
from integration import GithubWorkflowRunConfig, GithubWorkflowRunSelector


@pytest.fixture
def resource_config() -> ResourceConfig:
    return GithubWorkflowRunConfig(
        kind=ObjectKind.WORKFLOW_RUN,
        selector=GithubWorkflowRunSelector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".full_name",
                    title=".name",
                    blueprint='"githubRepository"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def workflow_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> WorkflowRunWebhookProcessor:
    return WorkflowRunWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestWorkflowRunWebhookProcessor:
    @pytest.mark.parametrize(
        "github_event,action,result",
        [
            ("workflow_run", WORKFLOW_UPSERT_EVENTS[0], True),
            ("workflow_run", WORKFLOW_UPSERT_EVENTS[1], True),
            ("workflow_run", "unknown_action", False),
            ("invalid", WORKFLOW_UPSERT_EVENTS[0], False),
            ("invalid", "unknown_action", False),
        ],
    )
    async def test_should_process_event(
        self,
        workflow_webhook_processor: WorkflowRunWebhookProcessor,
        github_event: str,
        action: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": action},
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request

        assert await workflow_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, workflow_webhook_processor: WorkflowRunWebhookProcessor
    ) -> None:
        kinds = await workflow_webhook_processor.get_matching_kinds(
            workflow_webhook_processor.event
        )
        assert ObjectKind.WORKFLOW_RUN in kinds

    @pytest.mark.parametrize(
        "action",
        ["completed", "in_progress", "requested"],
    )
    async def test_handle_event_upserts(
        self,
        workflow_webhook_processor: WorkflowRunWebhookProcessor,
        resource_config: ResourceConfig,
        action: str,
    ) -> None:
        repo_data = {
            "id": 1,
            "name": "test-repo",
            "full_name": "test-org/test-repo",
            "description": "Test repository",
        }
        workflow_run = {"id": 1, "name": "test_worklow"}

        payload = {
            "action": action,
            "repository": repo_data,
            "workflow_run": workflow_run,
            "organization": {"login": "test-org"},
        }

        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = workflow_run

        with patch(
            "github.webhook.webhook_processors.workflow_run.workflow_run_webhook_processor.RestWorkflowRunExporter",
            return_value=mock_exporter,
        ):
            result = await workflow_webhook_processor.handle_event(
                payload, resource_config
            )

        mock_exporter.get_resource.assert_called_once_with(
            {"organization": "test-org", "repo_name": "test-repo", "run_id": 1}
        )

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [workflow_run]
        assert result.deleted_raw_results == []

    @pytest.mark.parametrize(
        "selector_status,run_status,run_conclusion,expect_deleted",
        [
            (["in_progress"], "in_progress", None, False),
            (["failure"], "completed", "failure", False),
            (["in_progress"], "completed", "success", True),
            (["failure"], "in_progress", None, True),
            (["in_progress", "completed"], "completed", None, False),
            (["in_progress", "failure"], "completed", "success", True),
        ],
    )
    async def test_handle_event_status_filter(
        self,
        workflow_webhook_processor: WorkflowRunWebhookProcessor,
        selector_status: list[str],
        run_status: str,
        run_conclusion: str | None,
        expect_deleted: bool,
    ) -> None:
        config = GithubWorkflowRunConfig(
            kind=ObjectKind.WORKFLOW_RUN,
            selector=GithubWorkflowRunSelector(query="true", statuses=selector_status),  # type: ignore[arg-type]
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".id",
                        title=".name",
                        blueprint='"githubWorkflowRun"',
                        properties={},
                    )
                )
            ),
        )
        repo_data = {"id": 1, "name": "test-repo", "full_name": "test-org/test-repo"}
        workflow_run = {
            "id": 1,
            "name": "test_workflow",
            "status": run_status,
            "conclusion": run_conclusion,
        }
        payload = {
            "action": run_status,
            "repository": repo_data,
            "workflow_run": workflow_run,
            "organization": {"login": "test-org"},
        }

        if expect_deleted:
            result = await workflow_webhook_processor.handle_event(payload, config)
            assert bool(result.updated_raw_results) is False
            assert bool(result.deleted_raw_results) is True
        else:
            mock_exporter = AsyncMock()
            mock_exporter.get_resource.return_value = workflow_run
            with patch(
                "github.webhook.webhook_processors.workflow_run.workflow_run_webhook_processor.RestWorkflowRunExporter",
                return_value=mock_exporter,
            ):
                result = await workflow_webhook_processor.handle_event(payload, config)
            assert bool(result.updated_raw_results) is True
            assert bool(result.deleted_raw_results) is False

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "action": WORKFLOW_UPSERT_EVENTS[0],
                    "repository": {"name": "repo1"},
                    "workflow_run": {"id": 1, "name": "test"},
                    "organization": {"login": "test-org"},
                },
                True,
            ),
            (
                {
                    "action": WORKFLOW_UPSERT_EVENTS[0],
                    "repository": {"name": "repo2"},
                    "workflow_run": {"id": 2, "name": "test 2"},
                    "organization": {"login": "test-org"},
                },
                True,
            ),
            (
                {
                    "action": WORKFLOW_UPSERT_EVENTS[0],
                    "repository": {"name": "repo2"},
                    "organization": {"login": "test-org"},
                },
                False,
            ),  # missing workflow_run
            (
                {
                    "action": WORKFLOW_UPSERT_EVENTS[0],
                    "repository": {"name": "repo2"},
                    "workflow_run": {},
                    "organization": {"login": "test-org"},
                },
                False,
            ),  # missing workflow_run id
            ({"action": WORKFLOW_UPSERT_EVENTS[0]}, False),  # missing repository
            ({"repository": {"name": "repo4"}}, False),  # missing action
            (
                {
                    "action": WORKFLOW_UPSERT_EVENTS[0],
                    "repository": {},
                    "organization": {"login": "test-org"},
                },  # no repository name
                False,
            ),
        ],
    )
    async def test_validate_payload(
        self,
        workflow_webhook_processor: WorkflowRunWebhookProcessor,
        payload: Dict[str, str],
        expected: bool,
    ) -> None:
        result = await workflow_webhook_processor._validate_payload(payload)
        assert result is expected
