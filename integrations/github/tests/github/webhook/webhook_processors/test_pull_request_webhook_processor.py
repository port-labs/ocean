from typing import Any, Literal, AsyncGenerator
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from port_ocean.context.event import event_context

from github.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from github.helpers.utils import ObjectKind
from github.webhook.events import PULL_REQUEST_EVENTS
from github.core.options import SinglePullRequestOptions
from integration import (
    GithubPullRequestSelector,
    GithubPullRequestConfig,
    GithubFilePattern,
    GithubFileResourceConfig,
    GithubFileSelector,
    RepositoryBranchMapping,
    GithubPortAppConfig,
)
from github.core.exporters.file_exporter.utils import ResourceConfigToPatternMapping


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
def pull_request_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> PullRequestWebhookProcessor:
    return PullRequestWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def resource_config() -> GithubPullRequestConfig:
    return GithubPullRequestConfig(
        kind="pull-request",
        selector=GithubPullRequestSelector(query="true", state="open"),
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
class TestPullRequestWebhookProcessor:
    async def test_should_process_event_valid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "pull_request"}
        mock_event.payload = {"action": "opened"}

        assert (
            await pull_request_webhook_processor._should_process_event(mock_event)
            is True
        )

    async def test_should_process_event_invalid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.headers = {"x-github-event": "some_other_event"}

        assert (
            await pull_request_webhook_processor._should_process_event(mock_event)
            is False
        )

    async def test_get_matching_kinds(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:
        mock_event = MagicMock(spec=WebhookEvent)

        kinds = await pull_request_webhook_processor.get_matching_kinds(mock_event)
        assert kinds == [ObjectKind.PULL_REQUEST]

    async def test_validate_payload_valid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:

        # Valid upsert payload
        for action in PULL_REQUEST_EVENTS:
            payload = {
                "action": action,
                "pull_request": {"number": 101},
                "repository": {"name": "test-repo"},
            }
            assert (
                await pull_request_webhook_processor._validate_payload(payload) is True
            )

    async def test_validate_payload_invalid(
        self, pull_request_webhook_processor: PullRequestWebhookProcessor
    ) -> None:

        # Missing pull_request
        payload = {"action": "opened", "repository": {"name": "test-repo"}}
        assert await pull_request_webhook_processor._validate_payload(payload) is False

        # Missing pull request number
        payload = {
            "action": "opened",
            "pull_request": {},
            "repository": {"name": "test-repo"},
        }
        assert await pull_request_webhook_processor._validate_payload(payload) is False

    @pytest.mark.parametrize(
        "selector_state,action,expected_update,expected_delete",
        [
            ("open", "opened", True, False),
            ("open", "closed", False, True),
            ("closed", "opened", True, False),
            ("closed", "closed", True, False),
            ("all", "opened", True, False),
            ("all", "closed", True, False),
        ],
    )
    async def test_handle_event_with_selector_state(
        self,
        selector_state: Literal["open", "closed", "all"],
        action: str,
        expected_update: bool,
        expected_delete: bool,
        resource_config: GithubPullRequestConfig,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        # Configure resource_config with the specified selector state
        resource_config.selector.state = selector_state

        # Test pull request data
        pr_data = {
            "id": 1,
            "number": 101,
            "title": "Test PR",
            "state": "open" if action == "opened" else "closed",
            "base": {"sha": "base-sha-123"},
            "head": {"sha": "head-sha-456"},
        }

        repo_data = {"name": "test-repo", "full_name": "test-org/test-repo"}

        payload = {"action": action, "pull_request": pr_data, "repository": repo_data}

        # Create updated PR data that would be returned by the exporter
        updated_pr_data = {**pr_data, "additional_data": "from_api"}

        # Mock the exporter
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = updated_pr_data

        with (
            patch(
                "github.webhook.webhook_processors.pull_request_webhook_processor.RestPullRequestExporter",
                return_value=mock_exporter,
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_webhook_processor.get_file_validation_mappings",
                return_value=[],
            ),
        ):
            async with event_context("test_event") as event:
                # Set up empty port app config
                event.port_app_config = mock_port_app_config

                result = await pull_request_webhook_processor.handle_event(
                    payload, resource_config
                )

                # Verify results based on expected behavior
                assert isinstance(result, WebhookEventRawResults)

                if expected_update:
                    assert result.updated_raw_results == [updated_pr_data]
                    assert result.deleted_raw_results == []
                    mock_exporter.get_resource.assert_called_once_with(
                        SinglePullRequestOptions(repo_name="test-repo", pr_number=101)
                    )
                elif expected_delete:
                    assert result.updated_raw_results == []
                    assert result.deleted_raw_results == [pr_data]
                    # Should not call get_resource when deleting
                    mock_exporter.get_resource.assert_not_called()

    async def test_handle_file_validation_no_validation_mappings(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        mock_payload: dict[str, Any],
        mock_port_app_config: GithubPortAppConfig,
    ) -> None:
        """Test file validation when no validation mappings are found."""
        with patch(
            "github.webhook.webhook_processors.pull_request_webhook_processor.get_file_validation_mappings",
            return_value=[],
        ):
            async with event_context("test_event") as event:
                # Set up empty port app config
                event.port_app_config = mock_port_app_config
                # Should not raise any exceptions and should return early
                await pull_request_webhook_processor._handle_file_validation(
                    mock_payload
                )

    async def test_handle_file_validation_with_validation_mappings_no_changed_files(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        mock_payload: dict[str, Any],
        mock_port_app_config: GithubPortAppConfig,
        file_resource_config: GithubFileResourceConfig,
    ) -> None:
        """Test file validation when validation mappings exist but no files changed."""
        validation_mapping = ResourceConfigToPatternMapping(
            resource_config=file_resource_config,
            patterns=[
                file_resource_config.selector.files[0]
            ],  # Only the YAML pattern with validation_check=True
        )

        # Create a mock GitHub client with async send_api_request
        mock_github_client = MagicMock()
        mock_github_client.send_api_request = AsyncMock(return_value={"files": []})

        with (
            patch(
                "github.webhook.webhook_processors.pull_request_webhook_processor.get_file_validation_mappings",
                return_value=[validation_mapping],
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_webhook_processor.create_github_client",
                return_value=mock_github_client,
            ),
        ):
            async with event_context("test_event") as event:
                # Set up port app config in event context
                event.port_app_config = mock_port_app_config
                # Should not raise any exceptions and should return early due to no changed files
                await pull_request_webhook_processor._handle_file_validation(
                    mock_payload
                )

                # Verify that send_api_request was called
                assert mock_github_client.send_api_request.called

    async def test_handle_file_validation_with_validation_mappings_and_changed_files(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        mock_payload: dict[str, Any],
        mock_port_app_config: GithubPortAppConfig,
        file_resource_config: GithubFileResourceConfig,
    ) -> None:
        """Test file validation when validation mappings exist and files have changed."""

        validation_mapping = ResourceConfigToPatternMapping(
            resource_config=file_resource_config,
            patterns=[file_resource_config.selector.files[0]],
        )

        # Create proper async generator mocks
        async def mock_file_generator() -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [{"path": "config.yaml", "repository": {"name": "test-repo"}}]

        with (
            patch(
                "github.webhook.webhook_processors.pull_request_webhook_processor.get_file_validation_mappings",
                return_value=[validation_mapping],
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_webhook_processor.create_github_client",
                return_value=MagicMock(),
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_webhook_processor.RestPullRequestExporter",
            ) as mock_pr_exporter_class,
            patch(
                "github.webhook.webhook_processors.pull_request_webhook_processor.FileValidationService",
            ) as mock_validation_service_class,
        ):
            # Create the actual exporter instance
            from github.core.exporters.file_exporter.core import RestFileExporter
            from github.clients.client_factory import create_github_client

            rest_client = create_github_client()
            file_exporter = RestFileExporter(rest_client)

            with (
                patch.object(
                    file_exporter, "fetch_commit_diff", new_callable=AsyncMock
                ) as mock_fetch_diff,
                patch.object(
                    file_exporter,
                    "get_paginated_resources",
                    return_value=mock_file_generator(),
                ) as mock_get_resources,
            ):

                # Mock the RestFileExporter constructor to return our mocked instance
                with patch(
                    "github.webhook.webhook_processors.pull_request_webhook_processor.RestFileExporter",
                    return_value=file_exporter,
                ):
                    # Mock the PR exporter and validation service
                    mock_pr_exporter = AsyncMock()
                    mock_pr_exporter_class.return_value = mock_pr_exporter

                    mock_validation_service = AsyncMock()
                    mock_validation_service_class.return_value = mock_validation_service

                    async with event_context("test_event") as event:
                        event.port_app_config = mock_port_app_config
                        await pull_request_webhook_processor._handle_file_validation(
                            mock_payload
                        )

                        assert mock_fetch_diff.called
                        assert mock_get_resources.called
                        assert (
                            mock_validation_service.validate_pull_request_files.called
                        )

                        # Verify that validation service was created and called
                        mock_validation_service_class.assert_called_once_with(
                            mock_pr_exporter
                        )
                        mock_validation_service.validate_pull_request_files.assert_called_once()

    async def test_handle_file_validation_exception_handling(
        self,
        pull_request_webhook_processor: PullRequestWebhookProcessor,
        mock_payload: dict[str, Any],
        mock_port_app_config: GithubPortAppConfig,
        file_resource_config: GithubFileResourceConfig,
    ) -> None:
        """Test file validation handles exceptions gracefully."""
        validation_mapping = ResourceConfigToPatternMapping(
            resource_config=file_resource_config,
            patterns=[file_resource_config.selector.files[0]],
        )

        with (
            patch(
                "github.webhook.webhook_processors.pull_request_webhook_processor.get_file_validation_mappings",
                return_value=[validation_mapping],
            ),
            patch(
                "github.webhook.webhook_processors.pull_request_webhook_processor.create_github_client",
                side_effect=Exception("GitHub client creation failed"),
            ),
        ):
            async with event_context("test_event") as event:
                # Set up port app config in event context
                event.port_app_config = mock_port_app_config
                # Should raise the exception since it's not handled in the method
                with pytest.raises(Exception, match="GitHub client creation failed"):
                    await pull_request_webhook_processor._handle_file_validation(
                        mock_payload
                    )
