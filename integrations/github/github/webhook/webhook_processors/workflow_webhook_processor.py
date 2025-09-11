from loguru import logger
from github.core.exporters.workflows_exporter import RestWorkflowExporter
from github.core.options import SingleWorkflowOptions
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.helpers.utils import fetch_commit_diff, extract_changed_files


class WorkflowWebhookProcessor(BaseRepositoryWebhookProcessor):
    """
    Processes push events to detect changes to GitHub Actions workflow files.
    When workflow files are modified, added, or removed, this processor updates
    the corresponding workflow entities in Port.
    """

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Only process push events that contain workflow file changes."""

        if event.headers.get("x-github-event") != "push":
            return False

        for commit in event.payload["commits"]:
            for file in commit.get("modified", []):
                if self._is_workflow_file(file):
                    return True
            for file in commit.get("added", []):
                if self._is_workflow_file(file):
                    return True

        return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.WORKFLOW]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle push events that modify workflow files.
        Fetches updated workflow data and returns it for upserting into Port.
        """
        repo = payload["repository"]
        repo_name = repo["name"]

        rest_client = create_github_client()
        commit_diff = await fetch_commit_diff(
            rest_client, repo_name, payload["before"], payload["after"]
        )
        _, changed_workflow_files = extract_changed_files(commit_diff["files"])

        logger.info(
            f"Processing workflow changes in repository {repo_name}. "
            f"Changed workflow files: {list(changed_workflow_files)}"
        )

        workflows_to_upsert = []
        exporter = RestWorkflowExporter(rest_client)

        for changed_file in changed_workflow_files:
            workflow_name = self._extract_file_name(changed_file)
            options = SingleWorkflowOptions(
                repo_name=repo_name, workflow_id=workflow_name
            )

            workflow = await exporter.get_resource(options)
            workflows_to_upsert.append(workflow)

        logger.info(
            f"Fetched {len(workflows_to_upsert)} workflows from {repo_name} "
            f"due to workflow file changes"
        )

        return WebhookEventRawResults(
            updated_raw_results=workflows_to_upsert,
            deleted_raw_results=[],
        )

    async def _validate_payload(self, payload: EventPayload) -> bool:
        """Validate that the payload contains required push event data."""
        if not payload.get("commits"):
            return False

        if not payload.get("ref", "").startswith("refs/heads/"):
            return False

        return True

    def _is_workflow_file(self, file_path: str) -> bool:
        """
        Check if a file path represents a GitHub Actions workflow file.
        Workflow files are located in .github/workflows/ and have .yml or .yaml extension.
        """
        return file_path.startswith(".github/workflows/") and (
            file_path.endswith(".yml") or file_path.endswith(".yaml")
        )

    @staticmethod
    def _extract_file_name(filepath: str) -> str:
        parts = filepath.split("/")
        return parts[len(parts) - 1]
