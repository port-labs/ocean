import pytest
from unittest.mock import MagicMock

from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor
from webhook_processors.team_webhook_processor import TeamWebhookProcessor
from webhook_processors.workflow_webhook_processor import WorkflowRunWebhookProcessor
from kinds import Kinds

import webhook_processors.issue_webhook_processor as issue_module
import webhook_processors.pull_request_webhook_processor as pr_module
import webhook_processors.repository_webhook_processor as repo_module
import webhook_processors.team_webhook_processor as team_module
import webhook_processors.workflow_webhook_processor as workflow_module


class DummyWebhookEvent:
    def __init__(self, headers: dict, payload: dict):
        self.headers = headers
        self.payload = payload


@pytest.fixture
def dummy_event():
    return DummyWebhookEvent(headers={}, payload={})


@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    monkeypatch.setenv("github_token", "dummy_token")


async def async_gen(items):
    for item in items:
        yield item


class DummyGitHubClient:
    def __init__(self, results):
        self.results = results

    def fetch_single_github_resource(self, resource_type, **kwargs):
        return async_gen(self.results)


@pytest.fixture
def dummy_resource_config():
    return MagicMock()


class TestIssueWebhookProcessor:
    @pytest.fixture
    def processor(self, dummy_event):
        return IssueWebhookProcessor(dummy_event)

    async def test_should_process_event_true(self, processor):
        event = DummyWebhookEvent(
            headers={"x-github-event": "issues"},
            payload={"issue": {"title": "Test Issue"}},
        )
        result = await processor.should_process_event(event)
        assert result is True

    async def test_should_process_event_false(self, processor):
        event = DummyWebhookEvent(
            headers={"x-github-event": "issues"},
            payload={"issue": {"title": "Test Issue", "pull_request": {}}},
        )
        result = await processor.should_process_event(event)
        assert result is False

    async def test_get_matching_kinds(self, processor):
        event = DummyWebhookEvent(headers={}, payload={})
        kinds = await processor.get_matching_kinds(event)
        assert Kinds.ISSUE in kinds

    async def test_handle_event(self, processor, dummy_resource_config, monkeypatch):
        payload = {
            "issue": {"number": 123, "title": "Original Issue"},
            "repository": {"name": "repo1", "owner": {"login": "owner1"}},
        }
        updated_issue = {"number": 123, "title": "Updated Issue"}
        monkeypatch.setattr(
            issue_module,
            "create_github_client",
            lambda: DummyGitHubClient([updated_issue]),
        )
        results = await processor.handle_event(payload, dummy_resource_config)
        assert isinstance(results.updated_raw_results, list)
        assert results.deleted_raw_results == []

    async def test_handle_event_multiple_results(
        self, processor, dummy_resource_config, monkeypatch
    ):
        payload = {
            "issue": {"number": 123, "title": "Original Issue"},
            "repository": {"name": "repo1", "owner": {"login": "owner1"}},
        }
        updated_issue1 = {"number": 123, "title": "Updated Issue 1"}
        updated_issue2 = {"number": 123, "title": "Updated Issue 2"}
        monkeypatch.setattr(
            issue_module,
            "create_github_client",
            lambda: DummyGitHubClient([updated_issue1, updated_issue2]),
        )
        results = await processor.handle_event(payload, dummy_resource_config)
        assert isinstance(results.updated_raw_results, list)
        assert len(results.updated_raw_results) == 4

    async def test_authenticate_and_validate(self, processor):
        dummy_payload = {"dummy": "data"}
        dummy_headers = {"dummy": "header"}
        auth_result = await processor.authenticate(dummy_payload, dummy_headers)
        assert isinstance(auth_result, bool)
        valid = await processor.validate_payload(dummy_payload)
        assert valid is True


class TestPullRequestWebhookProcessor:
    @pytest.fixture
    def processor(self, dummy_event):
        return PullRequestWebhookProcessor(dummy_event)

    async def test_should_process_event_true(self, processor):
        event = DummyWebhookEvent(
            headers={"x-github-event": "pull_request"},
            payload={"pull_request": {"title": "PR Title"}},
        )
        result = await processor.should_process_event(event)
        assert result is True

    async def test_get_matching_kinds(self, processor):
        event = DummyWebhookEvent(headers={}, payload={})
        kinds = await processor.get_matching_kinds(event)
        assert Kinds.PULL_REQUEST in kinds

    async def test_handle_event(self, processor, dummy_resource_config, monkeypatch):
        payload = {
            "pull_request": {"number": 45, "title": "Original PR"},
            "repository": {"name": "repo1", "owner": {"login": "owner1"}},
        }
        updated_pr = {"number": 45, "title": "Updated PR"}
        monkeypatch.setattr(
            pr_module, "create_github_client", lambda: DummyGitHubClient([updated_pr])
        )
        results = await processor.handle_event(payload, dummy_resource_config)
        assert isinstance(results.updated_raw_results, list)

    async def test_authenticate_and_validate(self, processor):
        dummy_payload = {"dummy": "data"}
        dummy_headers = {"dummy": "header"}
        auth_result = await processor.authenticate(dummy_payload, dummy_headers)
        assert isinstance(auth_result, bool)
        valid = await processor.validate_payload(dummy_payload)
        assert valid is True


class TestRepositoryWebhookProcessor:
    @pytest.fixture
    def processor(self, dummy_event):
        return RepositoryWebhookProcessor(dummy_event)

    async def test_should_process_event(self, processor):
        event = DummyWebhookEvent(
            headers={"x-github-event": "repository"}, payload={"repository": {}}
        )
        result = await processor.should_process_event(event)
        assert result is True

    async def test_get_matching_kinds(self, processor):
        event = DummyWebhookEvent(headers={}, payload={})
        kinds = await processor.get_matching_kinds(event)
        assert Kinds.REPOSITORY in kinds

    async def test_handle_event_updated(
        self, processor, dummy_resource_config, monkeypatch
    ):
        repo = {"name": "repo1", "owner": {"login": "owner1"}}
        payload = {"action": "edited", "repository": repo}
        updated_repo = {"name": "repo1", "updated": True}
        monkeypatch.setattr(
            repo_module,
            "create_github_client",
            lambda: DummyGitHubClient([updated_repo]),
        )
        results = await processor.handle_event(payload, dummy_resource_config)
        assert isinstance(results.updated_raw_results, list)

    async def test_authenticate_and_validate(self, processor):
        dummy_payload = {"dummy": "data"}
        dummy_headers = {"dummy": "header"}
        auth_result = await processor.authenticate(dummy_payload, dummy_headers)
        assert isinstance(auth_result, bool)
        valid = await processor.validate_payload(dummy_payload)
        assert valid is True


class TestTeamWebhookProcessor:
    @pytest.fixture
    def processor(self, dummy_event):
        return TeamWebhookProcessor(dummy_event)

    async def test_should_process_event(self, processor):
        event = DummyWebhookEvent(
            headers={"x-github-event": "team"}, payload={"team": {}}
        )
        result = await processor.should_process_event(event)
        assert result is True

    async def test_get_matching_kinds(self, processor):
        event = DummyWebhookEvent(headers={}, payload={})
        kinds = await processor.get_matching_kinds(event)
        assert Kinds.TEAM in kinds

    async def test_handle_event(self, processor, dummy_resource_config, monkeypatch):
        payload = {
            "team": {"name": "Team Test", "slug": "team-test"},
            "organization": {"login": "org1"},
        }
        updated_team = {"name": "Team Test Updated", "slug": "team-test"}
        monkeypatch.setattr(
            team_module,
            "create_github_client",
            lambda: DummyGitHubClient([updated_team]),
        )
        results = await processor.handle_event(payload, dummy_resource_config)
        assert isinstance(results.updated_raw_results, list)

    async def test_authenticate_and_validate(self, processor):
        dummy_payload = {"dummy": "data"}
        dummy_headers = {"dummy": "header"}
        auth_result = await processor.authenticate(dummy_payload, dummy_headers)
        assert isinstance(auth_result, bool)
        valid = await processor.validate_payload(dummy_payload)
        assert valid is True


class TestWorkflowRunWebhookProcessor:
    @pytest.fixture
    def processor(self, dummy_event):
        return WorkflowRunWebhookProcessor(dummy_event)

    async def test_should_process_event(self, processor):
        event = DummyWebhookEvent(
            headers={"x-github-event": "workflow_run"}, payload={"workflow_run": {}}
        )
        result = await processor.should_process_event(event)
        assert result is True

    async def test_get_matching_kinds(self, processor):
        event = DummyWebhookEvent(headers={}, payload={})
        kinds = await processor.get_matching_kinds(event)
        assert Kinds.WORKFLOW in kinds

    async def test_handle_event(self, processor, dummy_resource_config, monkeypatch):
        workflow_run = {"id": 789, "name": "CI Build"}
        payload = {
            "workflow_run": workflow_run,
            "repository": {"name": "repo1", "owner": {"login": "owner1"}},
        }
        updated_run = {"id": 789, "name": "CI Build Updated"}
        monkeypatch.setattr(
            workflow_module,
            "create_github_client",
            lambda: DummyGitHubClient([updated_run]),
        )
        results = await processor.handle_event(payload, dummy_resource_config)
        assert isinstance(results.updated_raw_results, list)

    async def test_authenticate_and_validate(self, processor):
        dummy_payload = {"dummy": "data"}
        dummy_headers = {"dummy": "header"}
        auth_result = await processor.authenticate(dummy_payload, dummy_headers)
        assert isinstance(auth_result, bool)
        valid = await processor.validate_payload(dummy_payload)
        assert valid is True
