import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors.deployment_webhook_processor import (
    DeploymentWebhookProcessor,
)


@pytest.mark.asyncio
class TestDeploymentWebhookProcessor:
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
            "status_changed_at": "2026-04-28 21:50:00 +0200",
            "deployment_id": 15,
            "deployable_id": 796,
            "deployable_url": "https://gitlab.example.com/root/test-project/-/jobs/796",
            "environment": "production",
            "environment_tier": "production",
            "environment_slug": "production",
            "project": {
                "id": 30,
                "name": "test-project",
                "description": "",
                "web_url": "https://gitlab.example.com/root/test-project",
                "path_with_namespace": "root/test-project",
                "default_branch": "main",
                "homepage": "https://gitlab.example.com/root/test-project",
            },
        }

    async def test_get_matching_kinds_returns_deployment_and_deployment_status(
        self, processor: DeploymentWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        kinds = await processor.get_matching_kinds(mock_event)
        assert kinds == [ObjectKind.DEPLOYMENT, ObjectKind.DEPLOYMENT_STATUS]

    async def test_handle_event_fetches_deployment_and_enriches_with_full_project_from_payload(
        self, processor: DeploymentWebhookProcessor, deployment_payload: dict[str, Any]
    ) -> None:
        resource_config = MagicMock()
        project = deployment_payload["project"]
        deployment_id = deployment_payload["deployment_id"]
        project_id = project["id"]
        fetched_deployment = {
            "id": deployment_id,
            "iid": 1,
            "ref": "main",
            "sha": "99d03678b90d914dbb1b109132516d71a4a03ea8",
            "status": "success",
            "environment": {"id": 9, "name": "production"},
        }

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=fetched_deployment
        )

        result = await processor.handle_event(deployment_payload, resource_config)

        processor._gitlab_webhook_client.get_single_deployment.assert_called_once_with(
            project_id=project_id,
            deployment_id=deployment_id,
        )
        assert len(result.updated_raw_results) == 1
        enriched = result.updated_raw_results[0]
        assert enriched["id"] == deployment_id
        assert enriched["__project"] == project
        assert enriched["__project"]["path_with_namespace"] == "root/test-project"
        assert not result.deleted_raw_results

    async def test_handle_event_returns_empty_results_when_deployment_not_found(
        self, processor: DeploymentWebhookProcessor, deployment_payload: dict[str, Any]
    ) -> None:
        resource_config = MagicMock()

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=None
        )

        result = await processor.handle_event(deployment_payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_handle_event_enriches_with_full_project_object_not_just_path(
        self, processor: DeploymentWebhookProcessor, deployment_payload: dict[str, Any]
    ) -> None:
        resource_config = MagicMock()
        fetched_deployment = {"id": 15, "status": "success"}

        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.get_single_deployment = AsyncMock(
            return_value=fetched_deployment
        )

        result = await processor.handle_event(deployment_payload, resource_config)

        injected_project = result.updated_raw_results[0]["__project"]
        assert injected_project["name"] == "test-project"
        assert (
            injected_project["web_url"]
            == "https://gitlab.example.com/root/test-project"
        )
        assert injected_project["default_branch"] == "main"
