from typing import Dict, Any
import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.deployment_webhook_processor import (
    DeploymentWebhookProcessor,
)
from github.core.options import SingleDeploymentOptions, SingleEnvironmentOptions
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from github.helpers.utils import ObjectKind


@pytest.fixture
def deployment_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.DEPLOYMENT,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".description",
                    blueprint='"deployment"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def environment_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind=ObjectKind.ENVIRONMENT,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".name",
                    title=".name",
                    blueprint='"githubRepoEnvironment"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def deployment_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> DeploymentWebhookProcessor:
    return DeploymentWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestDeploymentWebhookProcessor:
    @pytest.mark.parametrize(
        "github_event,result",
        [
            ("deployment", True),
            ("deployment_status", True),
            ("push", False),
            ("pull_request", False),
        ],
    )
    async def test_should_process_event(
        self,
        deployment_webhook_processor: DeploymentWebhookProcessor,
        github_event: str,
        result: bool,
    ) -> None:
        mock_request = AsyncMock()
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={},
            headers={"x-github-event": github_event},
        )
        event._original_request = mock_request

        assert await deployment_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, deployment_webhook_processor: DeploymentWebhookProcessor
    ) -> None:
        kinds = await deployment_webhook_processor.get_matching_kinds(
            deployment_webhook_processor.event
        )
        assert set(kinds) == {ObjectKind.DEPLOYMENT, ObjectKind.ENVIRONMENT}

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {
                    "deployment": {
                        "id": 123,
                        "environment": "production",
                    }
                },
                True,
            ),
            (
                {
                    "deployment": {
                        "id": None,
                        "environment": None,
                    }
                },
                False,
            ),
            (
                {
                    "deployment": {
                        "id": 123,
                        "environment": None,
                    }
                },
                False,
            ),
            (
                {
                    "deployment": {
                        "id": None,
                        "environment": "production",
                    }
                },
                False,
            ),
            ({"deployment": {}}, False),  # missing required fields
            ({}, False),  # missing deployment
        ],
    )
    async def test_validate_payload(
        self,
        deployment_webhook_processor: DeploymentWebhookProcessor,
        payload: Dict[str, Any],
        expected: bool,
    ) -> None:
        result = await deployment_webhook_processor._validate_payload(payload)
        assert result is expected

    @pytest.mark.parametrize(
        "resource_config_name,expected_data",
        [
            (
                "deployment_resource_config",
                {
                    "id": 123,
                    "environment": "production",
                    "ref": "main",
                    "sha": "abc123",
                    "description": "Deploy to production",
                    "url": "https://github.com/org/repo/deployments/123",
                    "created_at": "2024-03-20T10:00:00Z",
                    "transient_environment": False,
                    "production_environment": True,
                    "__repository": "test-repo",
                },
            ),
            (
                "environment_resource_config",
                {
                    "name": "production",
                    "url": "https://github.com/org/repo/environments/production",
                    "created_at": "2024-03-20T10:00:00Z",
                    "updated_at": "2024-03-20T10:00:00Z",
                    "protected_branches": True,
                    "custom_branch_policies": True,
                    "__repository": "test-repo",
                },
            ),
        ],
    )
    async def test_handle_event(
        self,
        deployment_webhook_processor: DeploymentWebhookProcessor,
        resource_config_name: str,
        expected_data: Dict[str, Any],
        request: pytest.FixtureRequest,
    ) -> None:
        resource_config: ResourceConfig = request.getfixturevalue(resource_config_name)
        payload = {
            "action": "created",
            "deployment": {
                "id": 123,
                "environment": "production",
                "ref": "main",
                "sha": "abc123",
                "description": "Deploy to production",
                "url": "https://github.com/org/repo/deployments/123",
                "created_at": "2024-03-20T10:00:00Z",
                "transient_environment": False,
                "production_environment": True,
            },
            "repository": {"name": "test-repo"},
        }

        # Mock the appropriate exporter based on resource config
        if resource_config.kind == ObjectKind.DEPLOYMENT:
            mock_exporter = AsyncMock()
            mock_exporter.get_resource.return_value = expected_data

            with patch(
                "github.webhook.webhook_processors.deployment_webhook_processor.RestDeploymentExporter",
                return_value=mock_exporter,
            ):
                result = await deployment_webhook_processor.handle_event(
                    payload, resource_config
                )

            # Verify exporter was called with correct options
            mock_exporter.get_resource.assert_called_once_with(
                SingleDeploymentOptions(repo_name="test-repo", id="123")
            )
        else:  # ObjectKind.ENVIRONMENT
            mock_exporter = AsyncMock()
            mock_exporter.get_resource.return_value = expected_data

            with patch(
                "github.webhook.webhook_processors.deployment_webhook_processor.RestEnvironmentExporter",
                return_value=mock_exporter,
            ):
                result = await deployment_webhook_processor.handle_event(
                    payload, resource_config
                )

            # Verify exporter was called with correct options
            mock_exporter.get_resource.assert_called_once_with(
                SingleEnvironmentOptions(repo_name="test-repo", name="production")
            )

        assert isinstance(result, WebhookEventRawResults)
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == expected_data
