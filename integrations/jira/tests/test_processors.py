import pytest
from unittest.mock import AsyncMock, patch
from jira.overrides import (
    JiraIssueSelector,
    JiraProjectResourceConfig,
    JiraProjectSelector,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.project_webhook_processor import (
    ProjectWebhookProcessor,
)
from webhook_processors.user_webhook_processor import UserWebhookProcessor
from webhook_processors.version_webhook_processor import VersionWebhookProcessor
from typing import Any


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def jiraIssueWebhookProcessor(event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(event)


@pytest.fixture
def jiraUserWebhookProcessor(event: WebhookEvent) -> UserWebhookProcessor:
    return UserWebhookProcessor(event)


@pytest.fixture
def jiraProjectWebhookProcessor(event: WebhookEvent) -> ProjectWebhookProcessor:
    return ProjectWebhookProcessor(event)


@pytest.fixture
def jiraVersionWebhookProcessor(event: WebhookEvent) -> VersionWebhookProcessor:
    return VersionWebhookProcessor(event)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="repository",
        selector=JiraIssueSelector(query="type=issue", jql="project = TEST"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".name",
                    title=".name",
                    blueprint='"service"',
                    properties={
                        "url": ".links.html.href",
                        "defaultBranch": ".main_branch",
                    },
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def project_resource_config() -> JiraProjectResourceConfig:
    config = JiraProjectResourceConfig(
        kind="project",
        selector=JiraProjectSelector(query="true", expand="insight"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".key",
                    title=".name",
                    blueprint='"jiraProjectTest"',
                    properties={},
                    relations={},
                )
            )
        ),
    )
    config.selector.include_releases = True
    return config


@pytest.fixture
def project_resource_config_no_releases() -> JiraProjectResourceConfig:
    return JiraProjectResourceConfig(
        kind="project",
        selector=JiraProjectSelector(query="true", expand="insight"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".key",
                    title=".name",
                    blueprint='"jiraProjectTest"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


@pytest.mark.asyncio
async def test_should_process_event(
    jiraIssueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "jira:issue_created",
        },
        headers={},
    )
    assert await jiraIssueWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "jira:issue_updated",
        },
        headers={},
    )
    assert await jiraIssueWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "jira:project_created",
        },
        headers={},
    )
    assert await jiraIssueWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds(
    jiraIssueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await jiraIssueWebhookProcessor.get_matching_kinds(event) == ["issue"]


@pytest.mark.asyncio
async def test_authenticate(
    jiraIssueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    result = await jiraIssueWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload(
    jiraIssueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    result = await jiraIssueWebhookProcessor.validate_payload(
        {
            "webhookEvent": "jira:issue_created",
            "issue": {"key": "TEST-1", "id": "10001"},
        }
    )
    assert result is True

    assert await jiraIssueWebhookProcessor.validate_payload({}) is False
    assert (
        await jiraIssueWebhookProcessor.validate_payload(
            {"webhookEvent": "jira:issue_created"}
        )
        is False
    )
    assert (
        await jiraIssueWebhookProcessor.validate_payload({"issue": {"key": "TEST-1"}})
        is False
    )


@pytest.mark.asyncio
async def test_handleEvent_issueUpdated_noJqlFilterIssuesReturnedFromClient_updatedRawResultsReturnedCorrectly(
    jiraIssueWebhookProcessor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    resource_config.selector.jql = None  # type: ignore

    payload: dict[str, Any] = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123", "id": "12345"},
    }
    mock_issue: dict[str, Any] = {
        "key": "TEST-123",
        "fields": {"summary": "Test Issue"},
    }

    with patch(
        "webhook_processors.issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_reconciled_issues = AsyncMock(return_value=[mock_issue])
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        mock_client.get_reconciled_issues.assert_called_once_with(
            jql="key = TEST-123", issue_ids=[12345], fields="*all"
        )
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_issue


@pytest.mark.asyncio
async def test_handleEvent_issueUpdated_noJqlFilterIssuesNotReturnedFromClient_deletedRawResultsReturnedCorrectly(
    jiraIssueWebhookProcessor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    resource_config.selector.jql = None  # type: ignore

    payload: dict[str, Any] = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123", "id": "12345"},
    }

    with patch(
        "webhook_processors.issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_reconciled_issues = AsyncMock(return_value=[])
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        mock_client.get_reconciled_issues.assert_called_once_with(
            jql="key = TEST-123", issue_ids=[12345], fields="*all"
        )
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["issue"]


@pytest.mark.asyncio
async def test_handleEvent_issueUpdated_filterIssuesReturnedFromClient_updatedRawResultsReturnedCorrectly(
    jiraIssueWebhookProcessor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123", "id": "12345"},
    }
    mock_issue: dict[str, Any] = {
        "key": "TEST-123",
        "fields": {"summary": "Test Issue"},
    }

    with patch(
        "webhook_processors.issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_reconciled_issues = AsyncMock(return_value=[mock_issue])
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        mock_client.get_reconciled_issues.assert_called_once_with(
            jql="(project = TEST) AND key = TEST-123",
            issue_ids=[12345],
            fields="*all",
        )
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_issue


@pytest.mark.asyncio
async def test_handleEvent_issueUpdated_filterIssuesNotReturnedFromClient_deletedRawResultsReturnedCorrectly(
    jiraIssueWebhookProcessor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123", "id": "12345"},
    }

    with patch(
        "webhook_processors.issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_reconciled_issues = AsyncMock(return_value=[])
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        mock_client.get_reconciled_issues.assert_called_once_with(
            jql="(project = TEST) AND key = TEST-123",
            issue_ids=[12345],
            fields="*all",
        )
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["issue"]


@pytest.mark.asyncio
async def test_handleEvent_issueDeleted_deletedRawResultsReturnedCorrectly(
    jiraIssueWebhookProcessor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    resource_config.selector.jql = None  # type: ignore

    payload = {
        "webhookEvent": "jira:issue_deleted",
        "issue": {"key": "TEST-123", "id": "12345"},
    }

    with patch(
        "webhook_processors.issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_create_client.return_value = AsyncMock()

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["issue"]


@pytest.mark.asyncio
async def test_should_process_event_user(
    jiraUserWebhookProcessor: UserWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "user_created",
        },
        headers={},
    )
    assert await jiraUserWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "user_updated",
        },
        headers={},
    )
    assert await jiraUserWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "jira:issue_created",
        },
        headers={},
    )
    assert await jiraUserWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds_user(
    jiraUserWebhookProcessor: UserWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await jiraUserWebhookProcessor.get_matching_kinds(event) == ["user"]


@pytest.mark.asyncio
async def test_authenticate_user(
    jiraUserWebhookProcessor: UserWebhookProcessor,
) -> None:
    result = await jiraUserWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_user(
    jiraUserWebhookProcessor: UserWebhookProcessor,
) -> None:
    result = await jiraUserWebhookProcessor.validate_payload({})
    assert result is True


@pytest.mark.asyncio
async def test_handleEvent_userUpdated_userReturnedFromClient_updatedRawResultsReturnedCorrectly(
    jiraUserWebhookProcessor: UserWebhookProcessor, resource_config: ResourceConfig
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "user_updated",
        "user": {"accountId": "TEST-123"},
    }
    mock_user: dict[str, Any] = {
        "accountId": "TEST-123",
        "fields": {"summary": "Test Issue"},
    }

    with patch(
        "webhook_processors.user_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_single_user(*args: Any, **kwargs: Any) -> dict[str, Any]:
            assert args[0] == "TEST-123"
            return mock_user

        mock_client.get_single_user = mock_get_single_user
        mock_create_client.return_value = mock_client

        result = await jiraUserWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_user


@pytest.mark.asyncio
async def test_handleEvent_userUpdated_userNotReturnedFromClient_noRawResultsReturned(
    jiraUserWebhookProcessor: UserWebhookProcessor, resource_config: ResourceConfig
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "user_updated",
        "user": {"accountId": "TEST-123"},
    }

    with patch(
        "webhook_processors.user_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_single_user(*args: Any, **kwargs: Any) -> None:
            assert args[0] == "TEST-123"
            return None

        mock_client.get_single_user = mock_get_single_user
        mock_create_client.return_value = mock_client

        result = await jiraUserWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handleEvent_userDeleted_noRawResultsReturned(
    jiraUserWebhookProcessor: UserWebhookProcessor, resource_config: ResourceConfig
) -> None:
    payload = {"webhookEvent": "user_deleted", "user": {"accountId": "TEST-123"}}
    mock_user: dict[str, Any] = {
        "accountId": "TEST-123",
        "fields": {"summary": "Test Issue"},
    }

    with patch(
        "webhook_processors.user_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_single_user(*args: Any, **kwargs: Any) -> dict[str, Any]:
            assert args[0] == "TEST-123"
            return mock_user

        mock_client.get_single_user = mock_get_single_user
        mock_create_client.return_value = mock_client

        result = await jiraUserWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == mock_user


@pytest.mark.asyncio
async def test_should_process_event_project(
    jiraProjectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "project_created",
        },
        headers={},
    )
    assert await jiraProjectWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "project_updated",
        },
        headers={},
    )
    assert await jiraProjectWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "jira:issue_created",
        },
        headers={},
    )
    assert await jiraProjectWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds_project(
    jiraProjectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await jiraProjectWebhookProcessor.get_matching_kinds(event) == ["project"]


@pytest.mark.asyncio
async def test_authenticate_project(
    jiraProjectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    result = await jiraProjectWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_project(
    jiraProjectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    result = await jiraProjectWebhookProcessor.validate_payload({})
    assert result is True


@pytest.mark.asyncio
async def test_handleEvent_projectUpdated_projectReturnedFromClient_updatedRawResultsReturnedCorrectly(
    jiraProjectWebhookProcessor: ProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "project_updated",
        "project": {"key": "TEST"},
    }
    mock_project: dict[str, Any] = {"key": "TEST", "name": "Test Project"}

    with patch(
        "webhook_processors.project_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_single_project(*args: Any, **kwargs: Any) -> dict[str, Any]:
            assert args[0] == "TEST"
            return mock_project

        mock_client.get_single_project = mock_get_single_project
        mock_create_client.return_value = mock_client

        result = await jiraProjectWebhookProcessor.handle_event(
            payload, resource_config
        )

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_project


@pytest.mark.asyncio
async def test_handleEvent_projectUpdated_projectNotReturnedFromClient_noRawResultsReturned(
    jiraProjectWebhookProcessor: ProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "project_updated",
        "project": {"key": "TEST"},
    }

    with patch(
        "webhook_processors.project_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_single_project(*args: Any, **kwargs: Any) -> None:
            assert args[0] == "TEST"
            return None

        mock_client.get_single_project = mock_get_single_project
        mock_create_client.return_value = mock_client

        result = await jiraProjectWebhookProcessor.handle_event(
            payload, resource_config
        )

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_handleEvent_projectSoftDeleted_deletedRawResultsReturnedCorrectly(
    jiraProjectWebhookProcessor: ProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload = {"webhookEvent": "project_soft_deleted", "project": {"key": "TEST"}}

    with patch(
        "webhook_processors.project_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_single_project(*args: Any, **kwargs: Any) -> None:
            assert args[0] == "TEST"
            return None

        mock_client.get_single_project = mock_get_single_project
        mock_create_client.return_value = mock_client

        result = await jiraProjectWebhookProcessor.handle_event(
            payload, resource_config
        )

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["project"]


@pytest.mark.asyncio
async def test_handleEvent_issueUpdated_jqlFilterIsWrappedWithParentheses(
    jiraIssueWebhookProcessor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    resource_config.selector.jql = "(statusCategory != Done) OR (created >= -1w) OR (updated >= -1w)"  # type: ignore

    payload: dict[str, Any] = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123", "id": "12345"},
    }
    mock_issue: dict[str, Any] = {
        "key": "TEST-123",
        "fields": {"summary": "Test Issue"},
    }

    with patch(
        "webhook_processors.issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_reconciled_issues = AsyncMock(return_value=[mock_issue])
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        mock_client.get_reconciled_issues.assert_called_once_with(
            jql="((statusCategory != Done) OR (created >= -1w) OR (updated >= -1w)) AND key = TEST-123",
            issue_ids=[12345],
            fields="*all",
        )
        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == mock_issue


# ---------------------------------------------------------------------------
# VersionWebhookProcessor tests (version events refresh project releases)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_should_process_event_version(
    jiraVersionWebhookProcessor: VersionWebhookProcessor,
) -> None:
    for version_event in (
        "jira:version_created",
        "jira:version_updated",
        "jira:version_deleted",
        "jira:version_released",
        "jira:version_unreleased",
    ):
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": version_event},
            headers={},
        )
        assert await jiraVersionWebhookProcessor.should_process_event(event) is True

    for non_version_event in ("jira:issue_created", "project_created", "user_updated"):
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"webhookEvent": non_version_event},
            headers={},
        )
        assert await jiraVersionWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_get_matching_kinds_version_returns_project(
    jiraVersionWebhookProcessor: VersionWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await jiraVersionWebhookProcessor.get_matching_kinds(event) == ["project"]


@pytest.mark.asyncio
async def test_validate_payload_version_valid_with_id(
    jiraVersionWebhookProcessor: VersionWebhookProcessor,
) -> None:
    assert (
        await jiraVersionWebhookProcessor.validate_payload({"version": {"id": 1001}})
        is True
    )


@pytest.mark.asyncio
async def test_validate_payload_version_valid_with_project_id(
    jiraVersionWebhookProcessor: VersionWebhookProcessor,
) -> None:
    assert (
        await jiraVersionWebhookProcessor.validate_payload(
            {"version": {"projectId": 10600}}
        )
        is True
    )


@pytest.mark.asyncio
async def test_validate_payload_version_invalid_missing_version(
    jiraVersionWebhookProcessor: VersionWebhookProcessor,
) -> None:
    assert await jiraVersionWebhookProcessor.validate_payload({}) is False


@pytest.mark.asyncio
async def test_validate_payload_version_invalid_empty_version(
    jiraVersionWebhookProcessor: VersionWebhookProcessor,
) -> None:
    assert await jiraVersionWebhookProcessor.validate_payload({"version": {}}) is False


@pytest.mark.asyncio
async def test_handle_event_version_include_releases_true_refreshes_project(
    jiraVersionWebhookProcessor: VersionWebhookProcessor,
    project_resource_config: JiraProjectResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "jira:version_updated",
        "version": {"id": 1001, "projectId": 10600},
    }
    mock_project: dict[str, Any] = {
        "key": "PROJ1",
        "name": "Test Project",
        "__releases": [
            {"id": "1001", "name": "v1.0", "__projectKey": "PROJ1"},
        ],
    }

    with patch(
        "webhook_processors.version_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_project_with_releases = AsyncMock(return_value=mock_project)
        mock_create_client.return_value = mock_client

        result = await jiraVersionWebhookProcessor.handle_event(
            payload, project_resource_config
        )

        mock_client.get_project_with_releases.assert_called_once_with("10600")
        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["key"] == "PROJ1"
        assert "__releases" in result.updated_raw_results[0]
        assert len(result.updated_raw_results[0]["__releases"]) == 1


@pytest.mark.asyncio
async def test_handle_event_version_include_releases_false_returns_empty(
    jiraVersionWebhookProcessor: VersionWebhookProcessor,
    project_resource_config_no_releases: JiraProjectResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "jira:version_created",
        "version": {"id": 1002, "projectId": 10601},
    }

    with patch(
        "webhook_processors.version_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()
        mock_create_client.return_value = mock_client

        result = await jiraVersionWebhookProcessor.handle_event(
            payload, project_resource_config_no_releases
        )

        mock_client.get_project_with_releases.assert_not_called()
        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0
