import pytest
from unittest.mock import AsyncMock, patch

from jira.overrides import JiraIssueSelector
from port_ocean.core.handlers.port_app_config.models import EntityMapping, MappingsConfig, PortResourceConfig, ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from integrations.jira.webhook_processors.jira_issue_webhook_processor import JiraIssueWebhookProcessor


@pytest.fixture
def event():
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def jiraIssueWebhookProcessor(event: WebhookEvent):
    return JiraIssueWebhookProcessor(event)


@pytest.fixture
def resource_config():
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


def test_should_process_event(jiraIssueWebhookProcessor):
    # Test issue events
    event = WebhookEvent(trace_id= "test-trace-id", payload={"webhookEvent": "jira:issue_created", }, headers={})
    assert jiraIssueWebhookProcessor.should_process_event(event) is True

    event = WebhookEvent(trace_id= "test-trace-id", payload={"webhookEvent": "jira:issue_updated", }, headers={})
    assert jiraIssueWebhookProcessor.should_process_event(event) is True

    # Test non-issue events
    event = WebhookEvent(trace_id= "test-trace-id", payload={"webhookEvent": "jira:project_created", }, headers={})
    assert jiraIssueWebhookProcessor.should_process_event(event) is False


def test_get_matching_kinds(jiraIssueWebhookProcessor):
    event = WebhookEvent(trace_id= "test-trace-id", payload={}, headers={})
    assert jiraIssueWebhookProcessor.get_matching_kinds(event) == ["issue"]


@pytest.mark.asyncio
async def test_handle_event_deleted_issue(jiraIssueWebhookProcessor, resource_config):
    payload = {
        "webhookEvent": "jira:issue_deleted",
        "issue": {"key": "TEST-123", "fields": {}}
    }

    result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

    assert len(result.updated_raw_results) == 0
    assert len(result.deleted_raw_results) == 1
    assert result.deleted_raw_results[0] == payload["issue"]


@pytest.mark.asyncio
async def test_handle_event_updated_issue(jiraIssueWebhookProcessor, resource_config):
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123"}
    }

    mock_issue = {"key": "TEST-123", "fields": {"summary": "Test Issue"}}

    with patch("integrations.jira.webhook_processors.jira_issue_webhook_processor.create_jira_client") as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_paginated_issues.return_value = [[mock_issue]]
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        # Verify JQL construction
        mock_client.get_paginated_issues.assert_called_once_with(
            {"jql": "project = TEST AND key = TEST-123"}
        )

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_issue


@pytest.mark.asyncio
async def test_handle_event_issue_not_found(jiraIssueWebhookProcessor, resource_config):
    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123"}
    }

    with patch("integrations.jira.webhook_processors.jira_issue_webhook_processor.create_jira_client") as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_paginated_issues.return_value = [[]]  # Empty result
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 0
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0] == payload["issue"]


@pytest.mark.asyncio
async def test_authenticate(jiraIssueWebhookProcessor):
    result = await jiraIssueWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validate_payload(jiraIssueWebhookProcessor):
    result = await jiraIssueWebhookProcessor.validate_payload({})
    assert result is True


@pytest.mark.asyncio
async def test_handle_event_no_jql_filter(jiraIssueWebhookProcessor, resource_config):
    resource_config.selector.jql = None

    payload = {
        "webhookEvent": "jira:issue_updated",
        "issue": {"key": "TEST-123"}
    }

    mock_issue = {"key": "TEST-123", "fields": {"summary": "Test Issue"}}

    with patch("integrations.jira.webhook_processors.jira_issue_webhook_processor.create_jira_client") as mock_create_client:
        mock_client = AsyncMock()
        # Create an async iterator for get_paginated_issues
        async def mock_paginated_issues(*args, **kwargs):
            yield [mock_issue]
        mock_client.get_paginated_issues = mock_paginated_issues
        mock_create_client.return_value = mock_client

        result = await jiraIssueWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_issue
