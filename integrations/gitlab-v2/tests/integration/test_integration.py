import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEventRawResults,
    WebhookEvent,
)
from port_ocean.core.handlers.port_app_config.validators import (
    validate_and_get_config_schema,
)
from datetime import datetime
from pydantic import ValidationError
from integration import GitlabPortAppConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from gitlab.helpers.utils import GitLabDeploymentStatus
from integration import (
    GitlabIntegration,
    GitManipulationHandler,
    GitlabLiveEventsProcessorManager,
    PipelineQueryParams,
    GitLabDeploymentQueryParams,
    GitLabDeploymentSelector,
    GitLabDeploymentStatusSelector,
)


@pytest.fixture
def mock_context() -> MagicMock:
    context = MagicMock(spec=PortOceanContext)
    context.app = MagicMock()
    context.app.integration_router = MagicMock()
    context.config = MagicMock()
    context.config.max_event_processing_seconds = 60
    context.config.max_wait_seconds_before_shutdown = 30
    return context


@pytest.fixture
def mock_signal_handler() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        headers={"x-gitlab-event": "Push Hook"},
        payload={"project": {"id": "123"}, "event_name": "push"},
    )


@pytest.fixture
def mock_webhook_results() -> WebhookEventRawResults:
    return WebhookEventRawResults(
        updated_raw_results=[{"id": "123", "name": "test-project"}],
        deleted_raw_results=[],
    )


@pytest.fixture
def mock_resource_config() -> MagicMock:
    config = MagicMock(spec=ResourceConfig)
    config.kind = "project"
    config.selector = MagicMock()
    config.selector.query = ""
    config.selector.include_languages = False
    return config


async def test_gitlab_integration_uses_gitmanipulation_handler(
    mock_context: MagicMock, mock_signal_handler: AsyncMock
) -> None:
    """Test that GitlabIntegration uses GitManipulationHandler as its EntityProcessorClass"""
    # Arrange & Act
    with patch("integration.signal_handler", mock_signal_handler):
        integration = GitlabIntegration(mock_context)

        # Assert
        assert integration.EntityProcessorClass == GitManipulationHandler


async def test_gitlab_webhook_manager_uses_gitmanipulation_handler(
    mock_context: MagicMock, mock_signal_handler: AsyncMock
) -> None:
    """Test that GitlabLiveEventsProcessorManager uses GitManipulationHandler as its EntityProcessorClass"""
    # Arrange & Act
    with patch("integration.signal_handler", mock_signal_handler):
        integration = GitlabIntegration(mock_context)
        manager = integration.context.app.webhook_manager

        # Assert
        assert isinstance(manager, GitlabLiveEventsProcessorManager)
        assert manager.EntityProcessorClass == GitManipulationHandler


def test_gitlab_port_app_config_schema_generation_includes_all_resource_kinds() -> None:
    """Validates that schema generation succeeds and all supported resource kinds are present."""
    schema = validate_and_get_config_schema(GitlabPortAppConfig)

    assert schema, "Expected a non-empty schema for GitlabPortAppConfig"

    schema_str = str(schema)
    expected_kinds = {
        "project",
        "group",
        "issue",
        "group-with-members",
        "member",
        "folder",
        "file",
        "merge-request",
        "tag",
        "release",
        "pipeline",
        "job",
        "deployment",
        "deployment-status",
    }

    missing_kinds = {kind for kind in expected_kinds if kind not in schema_str}
    assert not missing_kinds, f"Missing resource kinds in schema: {missing_kinds}"


def test_generate_query_params_excludes_unset_fields() -> None:
    """Fields that were never set should not appear in the generated params."""
    assert PipelineQueryParams().generate_query_params() == {}


def test_generate_query_params_excludes_explicit_none_values() -> None:
    """Fields explicitly set to None should still be excluded from the generated params."""
    assert PipelineQueryParams(name=None).generate_query_params() == {}


def test_generate_query_params_includes_only_set_fields() -> None:
    """Only fields that were explicitly assigned should be emitted, keyed by field name."""
    params = PipelineQueryParams(
        name="build",
        ref="main",
        status="success",
    ).generate_query_params()

    assert params == {"name": "build", "ref": "main", "status": "success"}


def test_generate_query_params_uses_snake_case_field_names_for_aliased_fields() -> None:
    """Generated params must use the snake_case field names expected by the Gitlab API, not the camelCase aliases."""
    params = PipelineQueryParams(
        updated_after="2024-01-01T00:00:00Z",
        updated_before="2024-02-01T00:00:00Z",
    ).generate_query_params()

    assert params == {
        "updated_after": "2024-01-01T00:00:00Z",
        "updated_before": "2024-02-01T00:00:00Z",
    }


def test_deployment_query_params_build_query_params_is_empty_when_nothing_set() -> None:
    assert GitLabDeploymentQueryParams().build_query_params() == {}


def test_deployment_query_params_build_query_params_includes_environment() -> None:
    params = GitLabDeploymentQueryParams(environment="production").build_query_params()
    assert params == {"environment": "production"}


def test_deployment_query_params_build_query_params_includes_status_as_string_value() -> (
    None
):
    params = GitLabDeploymentQueryParams(
        status=GitLabDeploymentStatus.SUCCESS
    ).build_query_params()
    assert params == {"status": "success"}


def test_deployment_query_params_build_query_params_includes_updated_after() -> None:
    params = GitLabDeploymentQueryParams(
        updated_after="2024-01-15T10:00:00Z"
    ).build_query_params()
    assert params == {"updated_after": "2024-01-15T10:00:00Z"}


def test_deployment_query_params_build_query_params_excludes_none_fields() -> None:
    params = GitLabDeploymentQueryParams(
        status=GitLabDeploymentStatus.FAILED
    ).build_query_params()
    assert "environment" not in params
    assert "updated_after" not in params


def test_deployment_query_params_build_query_params_excludes_empty_string_environment() -> (
    None
):
    params = GitLabDeploymentQueryParams(environment="").build_query_params()
    assert "environment" not in params


def test_deployment_query_params_build_query_params_includes_all_set_fields() -> None:
    params = GitLabDeploymentQueryParams(
        environment="staging",
        status=GitLabDeploymentStatus.RUNNING,
        updated_after="2024-06-01T00:00:00Z",
    ).build_query_params()
    assert params == {
        "environment": "staging",
        "status": "running",
        "updated_after": "2024-06-01T00:00:00Z",
    }


def test_deployment_selector_build_query_params_is_empty_when_nothing_set() -> None:
    assert GitLabDeploymentSelector(query="true").build_query_params() == {}


def test_deployment_selector_build_query_params_merges_query_params() -> None:
    selector = GitLabDeploymentSelector(
        query="true",
        apiQueryParams=GitLabDeploymentQueryParams(
            status=GitLabDeploymentStatus.SUCCESS,
            environment="production",
        ),
    )
    params = selector.build_query_params()
    assert params["status"] == "success"
    assert params["environment"] == "production"


def test_deployment_selector_allows_any_status_when_no_finished_window() -> None:
    GitLabDeploymentSelector(
        query="true",
        apiQueryParams=GitLabDeploymentQueryParams(
            status=GitLabDeploymentStatus.FAILED
        ),
    )


def test_deployment_selector_allows_no_query_params_when_no_finished_window() -> None:
    GitLabDeploymentSelector(query="true")


def test_deployment_selector_accepts_finished_after_when_status_is_success() -> None:
    GitLabDeploymentSelector(
        query="true",
        apiQueryParams=GitLabDeploymentQueryParams(
            status=GitLabDeploymentStatus.SUCCESS
        ),
        finishedAfter=datetime(2024, 1, 1),
    )


def test_deployment_selector_accepts_finished_before_when_status_is_success() -> None:
    GitLabDeploymentSelector(
        query="true",
        apiQueryParams=GitLabDeploymentQueryParams(
            status=GitLabDeploymentStatus.SUCCESS
        ),
        finishedBefore=datetime(2024, 6, 1),
    )


def test_deployment_selector_rejects_finished_after_when_status_is_not_success() -> (
    None
):
    with pytest.raises(ValidationError):
        GitLabDeploymentSelector(
            query="true",
            apiQueryParams=GitLabDeploymentQueryParams(
                status=GitLabDeploymentStatus.FAILED
            ),
            finishedAfter=datetime(2024, 1, 1),
        )


def test_deployment_selector_rejects_finished_before_when_status_is_not_success() -> (
    None
):
    with pytest.raises(ValidationError):
        GitLabDeploymentSelector(
            query="true",
            apiQueryParams=GitLabDeploymentQueryParams(
                status=GitLabDeploymentStatus.RUNNING
            ),
            finishedBefore=datetime(2024, 6, 1),
        )


def test_deployment_selector_rejects_finished_after_when_query_params_absent() -> None:
    with pytest.raises(ValidationError):
        GitLabDeploymentSelector(
            query="true",
            finishedAfter=datetime(2024, 1, 1),
        )


def test_deployment_selector_build_query_params_sets_order_by_id_and_sort_asc_for_finished_after() -> (
    None
):
    finished_after = datetime(2024, 1, 1)
    selector = GitLabDeploymentSelector(
        query="true",
        apiQueryParams=GitLabDeploymentQueryParams(
            status=GitLabDeploymentStatus.SUCCESS
        ),
        finishedAfter=finished_after,
    )
    params = selector.build_query_params()
    assert params["order_by"] == "id"
    assert params["sort"] == "asc"
    assert params["finished_after"] == finished_after.isoformat()
    assert "finished_before" not in params


def test_deployment_selector_build_query_params_sets_order_by_id_and_sort_asc_for_finished_before() -> (
    None
):
    finished_before = datetime(2024, 6, 1)
    selector = GitLabDeploymentSelector(
        query="true",
        apiQueryParams=GitLabDeploymentQueryParams(
            status=GitLabDeploymentStatus.SUCCESS
        ),
        finishedBefore=finished_before,
    )
    params = selector.build_query_params()
    assert params["order_by"] == "id"
    assert params["sort"] == "asc"
    assert params["finished_before"] == finished_before.isoformat()
    assert "finished_after" not in params


def test_deployment_selector_build_query_params_merges_query_params_with_finished_window() -> (
    None
):
    finished_after = datetime(2024, 1, 1)
    finished_before = datetime(2024, 6, 1)
    selector = GitLabDeploymentSelector(
        query="true",
        apiQueryParams=GitLabDeploymentQueryParams(
            status=GitLabDeploymentStatus.SUCCESS,
            environment="production",
        ),
        finishedAfter=finished_after,
        finishedBefore=finished_before,
    )
    params = selector.build_query_params()
    assert params["status"] == "success"
    assert params["environment"] == "production"
    assert params["order_by"] == "id"
    assert params["sort"] == "asc"
    assert params["finished_after"] == finished_after.isoformat()
    assert params["finished_before"] == finished_before.isoformat()


def test_deployment_status_selector_build_query_params_returns_empty_when_no_query_params() -> (
    None
):
    assert GitLabDeploymentStatusSelector(query="true").build_query_params() == {}


def test_deployment_status_selector_build_query_params_delegates_to_query_params() -> (
    None
):
    selector = GitLabDeploymentStatusSelector(
        query="true",
        apiQueryParams=GitLabDeploymentQueryParams(
            status=GitLabDeploymentStatus.SUCCESS,
            environment="production",
        ),
    )
    assert selector.build_query_params() == {
        "status": "success",
        "environment": "production",
    }


def test_deployment_status_selector_build_query_params_forwards_updated_after() -> None:
    selector = GitLabDeploymentStatusSelector(
        query="true",
        apiQueryParams=GitLabDeploymentQueryParams(
            updated_after="2024-03-01T12:00:00Z"
        ),
    )
    assert selector.build_query_params() == {"updated_after": "2024-03-01T12:00:00Z"}
