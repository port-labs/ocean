import pytest
from unittest.mock import AsyncMock, MagicMock
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from azure_devops.webhooks.webhook_processors.pull_request_processor import (
    PullRequestWebhookProcessor,
)
from tests.conftest import mock_client_manager


@pytest.fixture
def pull_request_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> PullRequestWebhookProcessor:
    mock_client = MagicMock()
    _mgr = MagicMock()

    _mgr.get_client_for_org.return_value = mock_client
    mock_client._organization_base_url = "https://dev.azure.com/test"
    _mgr.get_clients.return_value = [mock_client]

    monkeypatch.setattr(
        "azure_devops.webhooks.webhook_processors.base_processor.AzureDevopsClientManager.create_from_ocean_config",
        lambda: _mgr,
    )
    return PullRequestWebhookProcessor(event)


@pytest.mark.asyncio
async def test_pull_request_should_process_event(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(
        trace_id="test-trace-id",
        payload={
            "eventType": "git.pullrequest.updated",
            "publisherId": "tfs",
            "resource": {"pullRequestId": "123"},
        },
        headers={},
    )
    assert await pull_request_processor.should_process_event(event) is True

    event.payload["eventType"] = "wrong.event"
    assert await pull_request_processor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_pull_request_get_matching_kinds(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await pull_request_processor.get_matching_kinds(event) == ["pull-request"]


@pytest.mark.asyncio
async def test_pull_request_validate_payload(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
) -> None:
    valid_payload = {
        "eventType": "git.pullrequest.updated",
        "publisherId": "tfs",
        "resource": {"pullRequestId": "123"},
    }
    assert await pull_request_processor.validate_payload(valid_payload) is True

    invalid_payload = {"missing": "fields"}
    assert await pull_request_processor.validate_payload(invalid_payload) is False


def _resource_config(
    *,
    enrich_with_commits: bool = False,
    enrich_with_review_discussion: bool = False,
) -> MagicMock:
    config = MagicMock()
    config.selector.enrich_with_commits = enrich_with_commits
    config.selector.enrich_with_review_discussion = enrich_with_review_discussion
    return config


def _pr_payload() -> dict[str, object]:
    return {
        "eventType": "git.pullrequest.updated",
        "publisherId": "tfs",
        "resource": {"pullRequestId": "123"},
    }


@pytest.mark.asyncio
async def test_pull_request_handle_event_skips_enrichment_when_flags_off(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetched_pr = {"pullRequestId": 123, "title": "Test PR"}
    mock_client = MagicMock()
    mock_client.get_pull_request = AsyncMock(return_value=fetched_pr)
    mock_client.enrich_pull_requests = AsyncMock()
    mock_client_manager(monkeypatch, mock_client)

    result = await pull_request_processor.handle_event(
        _pr_payload(), _resource_config()
    )

    mock_client.get_pull_request.assert_called_once_with("123")
    mock_client.enrich_pull_requests.assert_not_called()
    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["pullRequestId"] == 123
    assert not result.deleted_raw_results


@pytest.mark.asyncio
async def test_pull_request_handle_event_enriches_when_flags_enabled(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetched_pr = {
        "pullRequestId": 123,
        "title": "Test PR",
        "repository": {"id": "repo-guid", "project": {"id": "proj-guid"}},
    }
    enriched_pr = {
        **fetched_pr,
        "__commits": [{"commitId": "abc"}],
        "__threads": [{"id": 1}],
    }
    mock_client = MagicMock()
    mock_client.get_pull_request = AsyncMock(return_value=fetched_pr)
    mock_client.enrich_pull_requests = AsyncMock(return_value=[enriched_pr])
    mock_client_manager(monkeypatch, mock_client)

    result = await pull_request_processor.handle_event(
        _pr_payload(),
        _resource_config(
            enrich_with_commits=True,
            enrich_with_review_discussion=True,
        ),
    )

    mock_client.enrich_pull_requests.assert_called_once_with(
        [fetched_pr],
        enrich_with_commits=True,
        enrich_with_review_discussion=True,
        concurrency=1,
    )
    assert result.updated_raw_results[0]["__commits"] == [{"commitId": "abc"}]
    assert result.updated_raw_results[0]["__threads"] == [{"id": 1}]


@pytest.mark.asyncio
async def test_pull_request_handle_event_missing_pr_skips_upsert(
    pull_request_processor: PullRequestWebhookProcessor,
    mock_event_context: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_client = MagicMock()
    mock_client.get_pull_request = AsyncMock(return_value=None)
    mock_client.enrich_pull_requests = AsyncMock()
    mock_client_manager(monkeypatch, mock_client)

    result = await pull_request_processor.handle_event(
        _pr_payload(),
        _resource_config(enrich_with_commits=True),
    )

    mock_client.enrich_pull_requests.assert_not_called()
    assert not result.updated_raw_results
    assert not result.deleted_raw_results
