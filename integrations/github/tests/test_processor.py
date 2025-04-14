import os
import pytest
import asyncio
from unittest.mock import MagicMock
import httpx

# Import the processor classes from their proper packages.
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.pull_request_webhook_processor import PullRequestWebhookProcessor
from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor
from webhook_processors.team_webhook_processor import TeamWebhookProcessor
from webhook_processors.workflow_webhook_processor import WorkflowRunWebhookProcessor

from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from kinds import Kinds

# -----------------------------------------------------------------------------
# Dummy Event class to simulate a WebhookEvent with headers and payload.
# -----------------------------------------------------------------------------
class DummyWebhookEvent:
    def __init__(self, headers: dict, payload: dict):
        self.headers = headers
        self.payload = payload

# -----------------------------------------------------------------------------
# Fixture: Dummy event for processor instantiation.
# -----------------------------------------------------------------------------
@pytest.fixture
def dummy_event():
    # Minimal dummy event; real processors might not use self.event extensively.
    return DummyWebhookEvent(headers={}, payload={})

# -----------------------------------------------------------------------------
# Fixture: Set required environment variables.
# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    monkeypatch.setenv("github_token", "dummy_token")
    # Set other environment variables as needed.

# -----------------------------------------------------------------------------
# Helper async generator to yield items from a list.
# -----------------------------------------------------------------------------
async def async_gen(items):
    for item in items:
        yield item

# -----------------------------------------------------------------------------
# A dummy GitHub client that returns a preset list of results via fetch_resource.
# -----------------------------------------------------------------------------
class DummyGitHubClient:
    def __init__(self, results):
        self.results = results  # Expected to be a list of dictionaries.

    def fetch_resource(self, resource_type, **kwargs):
        return async_gen(self.results)

# -----------------------------------------------------------------------------
# Fixture: Dummy ResourceConfig (if needed).
# -----------------------------------------------------------------------------
@pytest.fixture
def dummy_resource_config():
    return MagicMock()

# -----------------------------------------------------------------------------
# Tests for IssueWebhookProcessor
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_issue_should_process_event_true(dummy_event):
    processor = IssueWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(
        headers={"x-github-event": "issues"},
        payload={"issue": {"title": "Test Issue"}}
    )
    result = await processor.should_process_event(event)
    assert result is True

@pytest.mark.asyncio
async def test_issue_should_process_event_false(dummy_event):
    processor = IssueWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(
        headers={"x-github-event": "issues"},
        payload={"issue": {"title": "Test Issue", "pull_request": {}}}
    )
    result = await processor.should_process_event(event)
    assert result is False

@pytest.mark.asyncio
async def test_issue_get_matching_kinds(dummy_event):
    processor = IssueWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(headers={}, payload={})
    kinds = await processor.get_matching_kinds(event)
    assert Kinds.ISSUE in kinds

@pytest.mark.asyncio
async def test_issue_handle_event(dummy_event, dummy_resource_config, monkeypatch):
    processor = IssueWebhookProcessor(dummy_event)
    payload = {
        "issue": {"number": 123, "title": "Original Issue"},
        "repository": {"name": "repo1", "owner": {"login": "owner1"}}
    }
    updated_issue = {"number": 123, "title": "Updated Issue"}
    # Instead of patching, use monkeypatch.setattr to override create_github_client.
    monkeypatch.setattr(
        "webhook_processors.issue_webhook_processor.create_github_client",
        lambda: DummyGitHubClient([updated_issue])
    )
    results = await processor.handle_event(payload, dummy_resource_config)
    # The webhook processor should override the original issue with the updated data.
    assert results.updated_raw_results[0]["title"] == "Updated Issue"
    assert results.deleted_raw_results == []

@pytest.mark.asyncio
async def test_issue_authenticate_and_validate(dummy_event):
    processor = IssueWebhookProcessor(dummy_event)
    dummy_payload = {"dummy": "data"}
    dummy_headers = {"dummy": "header"}
    auth_result = await processor.authenticate(dummy_payload, dummy_headers)
    assert isinstance(auth_result, bool)
    valid = await processor.validate_payload(dummy_payload)
    assert valid is True

# -----------------------------------------------------------------------------
# Tests for PullRequestWebhookProcessor
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pull_request_should_process_event_true(dummy_event):
    processor = PullRequestWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(
        headers={"x-github-event": "pull_request"},
        payload={"pull_request": {"title": "PR Title"}}
    )
    result = await processor.should_process_event(event)
    assert result is True

@pytest.mark.asyncio
async def test_pull_request_get_matching_kinds(dummy_event):
    processor = PullRequestWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(headers={}, payload={})
    kinds = await processor.get_matching_kinds(event)
    assert Kinds.PULL_REQUEST in kinds

@pytest.mark.asyncio
async def test_pull_request_handle_event(dummy_event, dummy_resource_config, monkeypatch):
    processor = PullRequestWebhookProcessor(dummy_event)
    payload = {
        "pull_request": {"number": 45, "title": "Original PR"},
        "repository": {"name": "repo1", "owner": {"login": "owner1"}}
    }
    updated_pr = {"number": 45, "title": "Updated PR"}
    monkeypatch.setattr(
        "webhook_processors.pull_request_webhook_processor.create_github_client",
        lambda: DummyGitHubClient([updated_pr])
    )
    results = await processor.handle_event(payload, dummy_resource_config)
    assert results.updated_raw_results[0]["title"] == "Updated PR"

@pytest.mark.asyncio
async def test_pull_request_authenticate_and_validate(dummy_event):
    processor = PullRequestWebhookProcessor(dummy_event)
    dummy_payload = {"dummy": "data"}
    dummy_headers = {"dummy": "header"}
    auth_result = await processor.authenticate(dummy_payload, dummy_headers)
    assert isinstance(auth_result, bool)
    valid = await processor.validate_payload(dummy_payload)
    assert valid is True

# -----------------------------------------------------------------------------
# Tests for RepositoryWebhookProcessor
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_repository_should_process_event(dummy_event):
    processor = RepositoryWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(
        headers={"x-github-event": "repository"},
        payload={"repository": {}}
    )
    result = await processor.should_process_event(event)
    assert result is True

@pytest.mark.asyncio
async def test_repository_get_matching_kinds(dummy_event):
    processor = RepositoryWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(headers={}, payload={})
    kinds = await processor.get_matching_kinds(event)
    assert Kinds.REPOSITORY in kinds

@pytest.mark.asyncio
async def test_repository_handle_event_updated(dummy_event, dummy_resource_config, monkeypatch):
    processor = RepositoryWebhookProcessor(dummy_event)
    repo = {"name": "repo1", "owner": {"login": "owner1"}}
    payload = {
        "action": "edited",
        "repository": repo
    }
    updated_repo = {"name": "repo1", "updated": True}
    monkeypatch.setattr(
        "webhook_processors.repository_webhook_processor.create_github_client",
        lambda: DummyGitHubClient([updated_repo])
    )
    results = await processor.handle_event(payload, dummy_resource_config)
    assert results.updated_raw_results[0].get("updated") is True

@pytest.mark.asyncio
async def test_repository_authenticate_and_validate(dummy_event):
    processor = RepositoryWebhookProcessor(dummy_event)
    dummy_payload = {"dummy": "data"}
    dummy_headers = {"dummy": "header"}
    auth_result = await processor.authenticate(dummy_payload, dummy_headers)
    assert isinstance(auth_result, bool)
    valid = await processor.validate_payload(dummy_payload)
    assert valid is True

# -----------------------------------------------------------------------------
# Tests for TeamWebhookProcessor
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_team_should_process_event(dummy_event):
    processor = TeamWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(
        headers={"x-github-event": "team"},
        payload={"team": {}}
    )
    result = await processor.should_process_event(event)
    assert result is True

@pytest.mark.asyncio
async def test_team_get_matching_kinds(dummy_event):
    processor = TeamWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(headers={}, payload={})
    kinds = await processor.get_matching_kinds(event)
    assert Kinds.TEAM in kinds

@pytest.mark.asyncio
async def test_team_handle_event(dummy_event, dummy_resource_config, monkeypatch):
    processor = TeamWebhookProcessor(dummy_event)
    payload = {
        "team": {"name": "Team Test", "slug": "team-test"},
        "organization": {"login": "org1"}
    }
    updated_team = {"name": "Team Test Updated", "slug": "team-test"}
    monkeypatch.setattr(
        "webhook_processors.team_webhook_processor.create_github_client",
        lambda: DummyGitHubClient([updated_team])
    )
    results = await processor.handle_event(payload, dummy_resource_config)
    assert results.updated_raw_results[0]["name"] == "Team Test Updated"

@pytest.mark.asyncio
async def test_team_authenticate_and_validate(dummy_event):
    processor = TeamWebhookProcessor(dummy_event)
    dummy_payload = {"dummy": "data"}
    dummy_headers = {"dummy": "header"}
    auth_result = await processor.authenticate(dummy_payload, dummy_headers)
    assert isinstance(auth_result, bool)
    valid = await processor.validate_payload(dummy_payload)
    assert valid is True

# -----------------------------------------------------------------------------
# Tests for WorkflowRunWebhookProcessor
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_run_should_process_event(dummy_event):
    processor = WorkflowRunWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(
        headers={"x-github-event": "workflow_run"},
        payload={"workflow_run": {}}
    )
    result = await processor.should_process_event(event)
    assert result is True

@pytest.mark.asyncio
async def test_workflow_run_get_matching_kinds(dummy_event):
    processor = WorkflowRunWebhookProcessor(dummy_event)
    event = DummyWebhookEvent(headers={}, payload={})
    kinds = await processor.get_matching_kinds(event)
    assert Kinds.WORKFLOW in kinds

@pytest.mark.asyncio
async def test_workflow_run_handle_event(dummy_event, dummy_resource_config, monkeypatch):
    processor = WorkflowRunWebhookProcessor(dummy_event)
    workflow_run = {"id": 789, "name": "CI Build"}
    payload = {
        "workflow_run": workflow_run,
        "repository": {"name": "repo1", "owner": {"login": "owner1"}}
    }
    updated_run = {"id": 789, "name": "CI Build Updated"}
    monkeypatch.setattr(
        "webhook_processors.workflow_webhook_processor.create_github_client",
        lambda: DummyGitHubClient([updated_run])
    )
    results = await processor.handle_event(payload, dummy_resource_config)
    assert results.updated_raw_results[0]["name"] == "CI Build Updated"

@pytest.mark.asyncio
async def test_workflow_run_authenticate_and_validate(dummy_event):
    processor = WorkflowRunWebhookProcessor(dummy_event)
    dummy_payload = {"dummy": "data"}
    dummy_headers = {"dummy": "header"}
    auth_result = await processor.authenticate(dummy_payload, dummy_headers)
    assert isinstance(auth_result, bool)
    valid = await processor.validate_payload(dummy_payload)
    assert valid is True
