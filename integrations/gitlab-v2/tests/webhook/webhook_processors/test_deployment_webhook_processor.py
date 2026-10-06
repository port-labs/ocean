import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from gitlab.helpers.utils import GitLabDeploymentStatus
from gitlab.webhook.webhook_processors.deployment_webhook_processor import (
    DeploymentWebhookProcessor,
)
from integration import (
    GitlabDeploymentQueryParams,
    GitlabDeploymentResourceConfig,
    GitlabDeploymentSelector,
)


@pytest.mark.asyncio
class TestDeploymentWebhookProcessorHandleEvent:

    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Deployment Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> DeploymentWebhookProcessor:
        return DeploymentWebhookProcessor(event=mock_event)

    @pytest.fixture
    def deployment_payload(self) -> dict[str, Any]:
        return {
            "object_kind": "deployment",
            "status": "success",
            "deployment_id": 15,
            "environment": "production",
            "project": {
                "id": 30,
                "name": "test-project",
                "path_with_namespace": "root/test-project",
                "default_branch": "main",
                "web_url": "https://gitlab.example.com/root/test-project",
            },
        }

    @pytest.fixture
    def resource_config(self) -> MagicMock:
        config = MagicMock(spec=GitlabDeploymentResourceConfig)
        config.selector = GitlabDeploymentSelector(query="true")
        return config

    @pytest.fixture
    def full_project(self) -> dict[str, Any]:
        return {
            "id": 30,
            "name": "test-project",
            "path_with_namespace": "root/test-project",
            "default_branch": "main",
            "web_url": "https://gitlab.example.com/root/test-project",
            "archived": False,
        }

    @pytest.fixture
    def fetched_deployment(self) -> dict[str, Any]:
        return {
            "id": 15,
            "iid": 1,
            "ref": "main",
            "sha": "99d03678b90d914dbb1b109132516d71a4a03ea8",
            "status": "success",
            "environment": {"id": 9, "name": "production"},
        }

    async def test_fetches_full_project_then_deployment_and_enriches(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        resource_config: MagicMock,
        full_project: dict[str, Any],
        fetched_deployment: dict[str, Any],
    ) -> None:
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=fetched_deployment
        )

        result = await processor.handle_event(deployment_payload, resource_config)

        processor._gitlab_webhook_client.get_project.assert_called_once_with("30")
        processor._gitlab_webhook_client.get_single_deployment.assert_called_once_with(
            project_id=30, deployment_id=15
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0]["__project"] == full_project

    async def test_skips_archived_project_when_include_only_active_projects_is_true(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        fetched_deployment: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            includeOnlyActiveProjects=True,
        )
        archived_project = {
            "id": 30,
            "path_with_namespace": "root/test-project",
            "archived": True,
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=archived_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=fetched_deployment
        )

        result = await processor.handle_event(deployment_payload, config)

        assert result.updated_raw_results == []
        processor._gitlab_webhook_client.get_single_deployment.assert_not_called()

    async def test_filters_out_non_matching_environment_from_query_params(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        full_project: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            apiQueryParams=GitlabDeploymentQueryParams(environment="staging"),
        )

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )

        result = await processor.handle_event(deployment_payload, config)

        assert result.updated_raw_results == []
        processor._gitlab_webhook_client.get_single_deployment.assert_not_called()

    async def test_filters_out_non_matching_status_from_query_params(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        full_project: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            apiQueryParams=GitlabDeploymentQueryParams(
                status=GitLabDeploymentStatus.FAILED
            ),
        )

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )

        result = await processor.handle_event(deployment_payload, config)

        assert result.updated_raw_results == []
        processor._gitlab_webhook_client.get_single_deployment.assert_not_called()

    async def test_returns_empty_when_project_not_found(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        resource_config: MagicMock,
    ) -> None:
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(return_value=None)

        result = await processor.handle_event(deployment_payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_returns_empty_when_deployment_not_found(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        resource_config: MagicMock,
        full_project: dict[str, Any],
    ) -> None:
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=None
        )

        result = await processor.handle_event(deployment_payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_filters_deployment_whose_updated_at_is_before_updated_after_window(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        full_project: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            apiQueryParams=GitlabDeploymentQueryParams(
                updated_after="2024-06-01T00:00:00Z"
            ),
        )
        deployment_before_window = {
            "id": 15,
            "status": "success",
            "updated_at": "2024-01-01T00:00:00Z",  # before updated_after
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=deployment_before_window
        )

        result = await processor.handle_event(deployment_payload, config)

        assert result.updated_raw_results == []

    async def test_passes_deployment_whose_updated_at_is_after_updated_after_window(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        full_project: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            apiQueryParams=GitlabDeploymentQueryParams(
                updated_after="2024-01-01T00:00:00Z"
            ),
        )
        deployment_within_window = {
            "id": 15,
            "status": "success",
            "updated_at": "2024-06-01T00:00:00Z",  # after updated_after
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=deployment_within_window
        )

        result = await processor.handle_event(deployment_payload, config)

        assert len(result.updated_raw_results) == 1

    async def test_filters_deployment_whose_updated_at_is_after_updated_before_window(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        full_project: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            apiQueryParams=GitlabDeploymentQueryParams(
                updated_before="2024-01-01T00:00:00Z"
            ),
        )
        deployment_after_window = {
            "id": 15,
            "status": "success",
            "updated_at": "2024-06-01T00:00:00Z",  # after updated_before
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=deployment_after_window
        )

        result = await processor.handle_event(deployment_payload, config)

        assert result.updated_raw_results == []

    async def test_passes_deployment_whose_updated_at_is_before_updated_before_window(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        full_project: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            apiQueryParams=GitlabDeploymentQueryParams(
                updated_before="2024-06-01T00:00:00Z"
            ),
        )
        deployment_within_window = {
            "id": 15,
            "status": "success",
            "updated_at": "2024-01-01T00:00:00Z",  # before updated_before
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=deployment_within_window
        )

        result = await processor.handle_event(deployment_payload, config)

        assert len(result.updated_raw_results) == 1

    async def test_filters_deployment_whose_finished_at_is_before_finished_after_window(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        full_project: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            apiQueryParams=GitlabDeploymentQueryParams(
                status=GitLabDeploymentStatus.SUCCESS,
                finished_after="2024-06-01T00:00:00Z",
            ),
        )
        deployment_before_window = {
            "id": 15,
            "status": "success",
            "updated_at": "2024-07-01T00:00:00Z",
            "deployable": {
                "finished_at": "2024-01-01T00:00:00Z"
            },  # before finished_after
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=deployment_before_window
        )

        result = await processor.handle_event(deployment_payload, config)

        assert result.updated_raw_results == []

    async def test_passes_deployment_whose_finished_at_is_after_finished_after_window(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        full_project: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            apiQueryParams=GitlabDeploymentQueryParams(
                status=GitLabDeploymentStatus.SUCCESS,
                finished_after="2024-01-01T00:00:00Z",
            ),
        )
        deployment_within_window = {
            "id": 15,
            "status": "success",
            "updated_at": "2024-06-01T00:00:00Z",
            "deployable": {
                "finished_at": "2024-06-01T00:00:00Z"
            },  # after finished_after
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=deployment_within_window
        )

        result = await processor.handle_event(deployment_payload, config)

        assert len(result.updated_raw_results) == 1

    async def test_filters_deployment_whose_finished_at_is_after_finished_before_window(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        full_project: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            apiQueryParams=GitlabDeploymentQueryParams(
                status=GitLabDeploymentStatus.SUCCESS,
                finished_before="2024-01-01T00:00:00Z",
            ),
        )
        deployment_after_window = {
            "id": 15,
            "status": "success",
            "updated_at": "2024-06-01T00:00:00Z",
            "deployable": {
                "finished_at": "2024-06-01T00:00:00Z"
            },  # after finished_before
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=deployment_after_window
        )

        result = await processor.handle_event(deployment_payload, config)

        assert result.updated_raw_results == []

    async def test_skips_finished_at_filter_when_deployable_is_null(
        self,
        processor: DeploymentWebhookProcessor,
        deployment_payload: dict[str, Any],
        full_project: dict[str, Any],
    ) -> None:
        config = MagicMock()
        config.selector = GitlabDeploymentSelector(
            query="true",
            apiQueryParams=GitlabDeploymentQueryParams(
                status=GitLabDeploymentStatus.SUCCESS,
                finished_after="2024-06-01T00:00:00Z",
            ),
        )
        api_triggered_deployment = {
            "id": 15,
            "status": "success",
            "updated_at": "2024-07-01T00:00:00Z",
            "deployable": None,  # API-triggered deployments have no deployable
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_project = AsyncMock(
            return_value=full_project
        )
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=api_triggered_deployment
        )

        result = await processor.handle_event(deployment_payload, config)

        assert len(result.updated_raw_results) == 1
