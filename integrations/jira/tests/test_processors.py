import pytest
from unittest.mock import AsyncMock, patch
from jira.overrides import JiraIssueSelector
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook_processors.jira_issue_webhook_processor import JiraIssueWebhookProcessor
from webhook_processors.jira_project_webhook_processor import (
    JiraProjectWebhookProcessor,
)
from webhook_processors.jira_user_webhook_processor import JiraUserWebhookProcessor
from typing import Any, AsyncGenerator


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def jiraIssueWebhookProcessor(event: WebhookEvent) -> JiraIssueWebhookProcessor:
    return JiraIssueWebhookProcessor(event)


@pytest.fixture
def jiraUserWebhookProcessor(event: WebhookEvent) -> JiraUserWebhookProcessor:
    return JiraUserWebhookProcessor(event)


@pytest.fixture
def jiraProjectWebhookProcessor(event: WebhookEvent) -> JiraProjectWebhookProcessor:
    return JiraProjectWebhookProcessor(event)


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


def test_should_process_event(
    jiraIssueWebhookProcessor: JiraIssueWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "jira:issue_created",
        },
        headers={},
    )
    assert jiraIssueWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "jira:issue_updated",
        },
        headers={},
    )
    assert jiraIssueWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "jira:project_created",
        },
        headers={},
    )
    assert jiraIssueWebhookProcessor.should_process_event(event) is False


def test_get_matching_kinds(
    jiraIssueWebhookProcessor: JiraIssueWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert jiraIssueWebhookProcessor.get_matching_kinds(event) == ["issue"]


@pytest.mark.asyncio
async def test_authenticate(
    jiraIssueWebhookProcessor: JiraIssueWebhookProcessor,
) -> None:
    result = await jiraIssueWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload(
    jiraIssueWebhookProcessor: JiraIssueWebhookProcessor,
) -> None:
    result = await jiraIssueWebhookProcessor.validate_payload({})
    assert result is True


@pytest.mark.asyncio
async def test_handleEvent_issueUpdated_noJqlFilterIssuesReturnedFromClient_updatedRawResultsReturnedCorrectly(
    jiraIssueWebhookProcessor: JiraIssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    resource_config.selector.jql = None  # type: ignore

    payload: dict[str, Any] = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123"},
    }
    mock_issue: dict[str, Any] = {
        "key": "TEST-123",
        "fields": {"summary": "Test Issue"},
    }

    with patch(
        "webhook_processors.jira_issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_paginated_issues(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            assert args[0] == {"jql": "key = TEST-123"}
            yield [mock_issue]

        mock_client.get_paginated_issues = mock_paginated_issues
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_issue


@pytest.mark.asyncio
async def test_handleEvent_issueUpdated_noJqlFilterIssuesNotReturnedFromClient_deletedRawResultsReturnedCorrectly(
    jiraIssueWebhookProcessor: JiraIssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    resource_config.selector.jql = None  # type: ignore

    payload: dict[str, Any] = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123"},
    }

    with patch(
        "webhook_processors.jira_issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_paginated_issues(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            assert args[0] == {"jql": "key = TEST-123"}
            yield []

        mock_client.get_paginated_issues = mock_paginated_issues
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["issue"]


@pytest.mark.asyncio
async def test_handleEvent_issueUpdated_filterIssuesReturnedFromClient_updatedRawResultsReturnedCorrectly(
    jiraIssueWebhookProcessor: JiraIssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123"},
    }
    mock_issue: dict[str, Any] = {
        "key": "TEST-123",
        "fields": {"summary": "Test Issue"},
    }

    with patch(
        "webhook_processors.jira_issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_paginated_issues(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            assert args[0] == {"jql": "project = TEST AND key = TEST-123"}
            yield [mock_issue]

        mock_client.get_paginated_issues = mock_paginated_issues
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_issue


@pytest.mark.asyncio
async def test_handleEvent_issueUpdated_filterIssuesNotReturnedFromClient_deletedRawResultsReturnedCorrectly(
    jiraIssueWebhookProcessor: JiraIssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123"},
    }

    with patch(
        "webhook_processors.jira_issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_paginated_issues(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            assert args[0] == {"jql": "project = TEST AND key = TEST-123"}
            yield []

        mock_client.get_paginated_issues = mock_paginated_issues
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["issue"]


@pytest.mark.asyncio
async def test_handleEvent_issueDeleted_deletedRawResultsReturnedCorrectly(
    jiraIssueWebhookProcessor: JiraIssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    resource_config.selector.jql = None  # type: ignore

    payload = {"webhookEvent": "jira:issue_deleted", "issue": {"key": "TEST-123"}}

    with patch(
        "webhook_processors.jira_issue_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_create_client.return_value = AsyncMock()

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["issue"]


def test_should_process_event_user(
    jiraUserWebhookProcessor: JiraUserWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "user_created",
        },
        headers={},
    )
    assert jiraUserWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "user_updated",
        },
        headers={},
    )
    assert jiraUserWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "jira:issue_created",
        },
        headers={},
    )
    assert jiraUserWebhookProcessor.should_process_event(event) is False


def test_get_matching_kinds_user(
    jiraUserWebhookProcessor: JiraUserWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert jiraUserWebhookProcessor.get_matching_kinds(event) == ["user"]


@pytest.mark.asyncio
async def test_authenticate_user(
    jiraUserWebhookProcessor: JiraUserWebhookProcessor,
) -> None:
    result = await jiraUserWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_user(
    jiraUserWebhookProcessor: JiraUserWebhookProcessor,
) -> None:
    result = await jiraUserWebhookProcessor.validate_payload({})
    assert result is True


@pytest.mark.asyncio
async def test_handleEvent_userUpdated_userReturnedFromClient_updatedRawResultsReturnedCorrectly(
    jiraUserWebhookProcessor: JiraUserWebhookProcessor, resource_config: ResourceConfig
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
        "webhook_processors.jira_user_webhook_processor.create_jira_client"
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
    jiraUserWebhookProcessor: JiraUserWebhookProcessor, resource_config: ResourceConfig
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "user_updated",
        "user": {"accountId": "TEST-123"},
    }

    with patch(
        "webhook_processors.jira_user_webhook_processor.create_jira_client"
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
    jiraUserWebhookProcessor: JiraUserWebhookProcessor, resource_config: ResourceConfig
) -> None:
    payload = {"webhookEvent": "user_deleted", "user": {"accountId": "TEST-123"}}
    mock_user: dict[str, Any] = {
        "accountId": "TEST-123",
        "fields": {"summary": "Test Issue"},
    }

    with patch(
        "webhook_processors.jira_user_webhook_processor.create_jira_client"
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
async def test_handleEvent_noWebhookUserEvent_noRawResultsReturned(
    jiraUserWebhookProcessor: JiraUserWebhookProcessor, resource_config: ResourceConfig
) -> None:
    payload: dict[str, Any] = {}

    with patch(
        "webhook_processors.jira_user_webhook_processor.create_jira_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_single_user(*args: Any, **kwargs: Any) -> str:
            assert args[0] == "TEST-123"
            return ""

        mock_client.get_single_user = mock_get_single_user
        mock_create_client.return_value = mock_client

        result = await jiraUserWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 0


def test_should_process_event_project(
    jiraProjectWebhookProcessor: JiraProjectWebhookProcessor,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "project_created",
        },
        headers={},
    )
    assert jiraProjectWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "project_updated",
        },
        headers={},
    )
    assert jiraProjectWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "webhookEvent": "jira:issue_created",
        },
        headers={},
    )
    assert jiraProjectWebhookProcessor.should_process_event(event) is False


def test_get_matching_kinds_project(
    jiraProjectWebhookProcessor: JiraProjectWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert jiraProjectWebhookProcessor.get_matching_kinds(event) == ["project"]


@pytest.mark.asyncio
async def test_authenticate_project(
    jiraProjectWebhookProcessor: JiraProjectWebhookProcessor,
) -> None:
    result = await jiraProjectWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload_project(
    jiraProjectWebhookProcessor: JiraProjectWebhookProcessor,
) -> None:
    result = await jiraProjectWebhookProcessor.validate_payload({})
    assert result is True


@pytest.mark.asyncio
async def test_handleEvent_projectUpdated_projectReturnedFromClient_updatedRawResultsReturnedCorrectly(
    jiraProjectWebhookProcessor: JiraProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "project_updated",
        "project": {"key": "TEST"},
    }
    mock_project: dict[str, Any] = {"key": "TEST", "name": "Test Project"}

    with patch(
        "webhook_processors.jira_project_webhook_processor.create_jira_client"
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
    jiraProjectWebhookProcessor: JiraProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "webhookEvent": "project_updated",
        "project": {"key": "TEST"},
    }

    with patch(
        "webhook_processors.jira_project_webhook_processor.create_jira_client"
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
    jiraProjectWebhookProcessor: JiraProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload = {"webhookEvent": "project_soft_deleted", "project": {"key": "TEST"}}

    with patch(
        "webhook_processors.jira_project_webhook_processor.create_jira_client"
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
async def test_handleEvent_noWebhookProjectEvent_noRawResultsReturned(
    jiraProjectWebhookProcessor: JiraProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {}

    result = await jiraProjectWebhookProcessor.handle_event(payload, resource_config)

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 0
