from typing import Any, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from port_ocean.context.event import event_context

from integration import (
    GithubFilePattern,
    GithubFileResourceConfig,
    GithubFileSelector,
    RepositoryBranchMapping,
    GithubPortAppConfig,
    GithubPullRequestConfig,
    GithubPullRequestSelector,
)
from github.webhook.webhook_processors.check_runs.check_runs_validator_webhook_processor import (
    CheckRunValidatorWebhookProcessor,
)
from github.webhook.webhook_processors.check_runs.file_validation import (
    ResourceConfigToPatternMapping,
)


class MockAsyncGenerator:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def __aiter__(self) -> "MockAsyncGenerator":
        self._iter = iter(self._values)
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


@pytest.fixture
def checkrun_validator_webhook_processor(
    mock_webhook_event: Any,
) -> CheckRunValidatorWebhookProcessor:
    return CheckRunValidatorWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def pull_request_resource_config() -> GithubPullRequestConfig:
    return GithubPullRequestConfig(
        kind="pull-request",
        selector=GithubPullRequestSelector(
            query="true",
            states=["open"],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".head.repo.name + (.id|tostring)",
                    title=".title",
                    blueprint='"githubPullRequest"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def file_resource_config() -> GithubFileResourceConfig:
    return GithubFileResourceConfig(
        kind="file",
        selector=GithubFileSelector(
            query="true",
            files=[
                GithubFilePattern(
                    path="*.yaml",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                    validationCheck=True,
                ),
                GithubFilePattern(
                    path="*.json",
                    repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                    validationCheck=False,
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
def mock_port_app_config(
    file_resource_config: GithubFileResourceConfig,
) -> GithubPortAppConfig:
    return GithubPortAppConfig(
        delete_dependent_entities=True,
        create_missing_related_entities=False,
        repository_type="all",
        resources=[file_resource_config],
    )


@pytest.fixture
def mock_payload() -> dict[str, Any]:
    return {
        "action": "opened",
        "repository": {"name": "test-repo"},
        "pull_request": {
            "number": 101,
            "base": {"sha": "base-sha-123"},
            "head": {"sha": "head-sha-456"},
        },
    }


@pytest.mark.asyncio
class TestCheckRunValidatorWebhookProcessor:
    async def test_handle_event_no_validation_mappings(
        self,
        checkrun_validator_webhook_processor: CheckRunValidatorWebhookProcessor,
        mock_payload: dict[str, Any],
        mock_port_app_config: GithubPortAppConfig,
        pull_request_resource_config: GithubPullRequestConfig,
    ) -> None:
        """Test handle_event when no validation mappings are found."""
        with patch(
            "github.webhook.webhook_processors.check_runs.check_runs_validator_webhook_processor.get_file_validation_mappings",
            return_value=[],
        ):
            async with event_context("test_event") as event:
                event.port_app_config = mock_port_app_config
                result = await checkrun_validator_webhook_processor.handle_event(
                    mock_payload, pull_request_resource_config
                )
                assert isinstance(result, WebhookEventRawResults)
                assert result.updated_raw_results == []
                assert result.deleted_raw_results == []

    async def test_handle_event_with_validation_mappings_no_changed_files(
        self,
        checkrun_validator_webhook_processor: CheckRunValidatorWebhookProcessor,
        mock_payload: dict[str, Any],
        mock_port_app_config: GithubPortAppConfig,
        file_resource_config: GithubFileResourceConfig,
        pull_request_resource_config: GithubPullRequestConfig,
    ) -> None:
        """Test handle_event when validation mappings exist but no files changed."""
        validation_mapping = ResourceConfigToPatternMapping(
            resource_config=file_resource_config,
            patterns=[file_resource_config.selector.files[0]],
        )

        with (
            patch(
                "github.webhook.webhook_processors.check_runs.check_runs_validator_webhook_processor.get_file_validation_mappings",
                return_value=[validation_mapping],
            ),
            patch(
                "github.webhook.webhook_processors.check_runs.check_runs_validator_webhook_processor.create_github_client",
                return_value=MagicMock(),
            ),
            patch(
                "github.webhook.webhook_processors.check_runs.check_runs_validator_webhook_processor.RestFileExporter",
            ) as mock_file_exporter_class,
        ):
            # Create mock file exporter
            mock_file_exporter = AsyncMock()
            mock_file_exporter.fetch_commit_diff.return_value = {"files": []}
            mock_file_exporter_class.return_value = mock_file_exporter

            async with event_context("test_event") as event:
                event.port_app_config = mock_port_app_config
                result = await checkrun_validator_webhook_processor.handle_event(
                    mock_payload, pull_request_resource_config
                )
                assert isinstance(result, WebhookEventRawResults)
                assert result.updated_raw_results == []
                assert result.deleted_raw_results == []

    async def test_handle_event_with_validation_mappings_and_changed_files(
        self,
        checkrun_validator_webhook_processor: CheckRunValidatorWebhookProcessor,
        mock_payload: dict[str, Any],
        mock_port_app_config: GithubPortAppConfig,
        file_resource_config: GithubFileResourceConfig,
        pull_request_resource_config: GithubPullRequestConfig,
    ) -> None:
        """Test handle_event when validation mappings exist and files have changed."""
        validation_mapping = ResourceConfigToPatternMapping(
            resource_config=file_resource_config,
            patterns=[file_resource_config.selector.files[0]],
        )

        # Create proper async generator mocks
        async def mock_file_generator(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [{"path": "config.yaml", "repository": {"name": "test-repo"}}]

        with (
            patch(
                "github.webhook.webhook_processors.check_runs.check_runs_validator_webhook_processor.get_file_validation_mappings",
                return_value=[validation_mapping],
            ),
            patch(
                "github.webhook.webhook_processors.check_runs.check_runs_validator_webhook_processor.create_github_client",
                return_value=MagicMock(),
            ),
            patch(
                "github.webhook.webhook_processors.check_runs.check_runs_validator_webhook_processor.RestFileExporter",
            ) as mock_file_exporter_class,
            patch(
                "github.webhook.webhook_processors.check_runs.check_runs_validator_webhook_processor.FileValidationService",
            ) as mock_validation_service_class,
        ):
            # Create mock file exporter
            mock_file_exporter = AsyncMock()
            mock_file_exporter.fetch_commit_diff.return_value = {
                "files": [{"filename": "config.yaml", "status": "modified"}]
            }
            mock_file_exporter.get_paginated_resources = mock_file_generator
            mock_file_exporter_class.return_value = mock_file_exporter

            # Create mock validation service
            mock_validation_service = AsyncMock()
            mock_validation_service_class.return_value = mock_validation_service

            async with event_context("test_event") as event:
                event.port_app_config = mock_port_app_config
                result = await checkrun_validator_webhook_processor.handle_event(
                    mock_payload, pull_request_resource_config
                )
                assert isinstance(result, WebhookEventRawResults)
                assert result.updated_raw_results == []
                assert result.deleted_raw_results == []

                # Verify that the file exporter methods were called
                mock_file_exporter.fetch_commit_diff.assert_called_once_with(
                    "test-repo", "base-sha-123", "head-sha-456"
                )

                # Verify that validation service was created and called
                mock_validation_service_class.assert_called_once()
                assert mock_validation_service.validate_pull_request_files.called

    async def test_handle_event_skipped_actions(
        self,
        checkrun_validator_webhook_processor: CheckRunValidatorWebhookProcessor,
        mock_port_app_config: GithubPortAppConfig,
        pull_request_resource_config: GithubPullRequestConfig,
    ) -> None:
        """Test handle_event skips certain pull request actions."""
        skipped_actions = ["closed", "merged", "assigned", "unassigned"]

        for action in skipped_actions:
            payload = {
                "action": action,
                "repository": {"name": "test-repo"},
                "pull_request": {
                    "number": 101,
                    "base": {"sha": "base-sha-123"},
                    "head": {"sha": "head-sha-456"},
                },
            }

            async with event_context("test_event") as event:
                event.port_app_config = mock_port_app_config
                result = await checkrun_validator_webhook_processor.handle_event(
                    payload, pull_request_resource_config
                )
                assert isinstance(result, WebhookEventRawResults)
                assert result.updated_raw_results == []
                assert result.deleted_raw_results == []
