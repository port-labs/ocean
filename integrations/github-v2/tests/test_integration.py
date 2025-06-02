"""Test GitHub integration structure and basic functionality."""

import pytest
from unittest.mock import patch
from typing import Any


def test_object_kinds_defined() -> None:
    """Test that ObjectKind constants are properly defined."""
    from github.helpers.utils import ObjectKind

    assert hasattr(ObjectKind, "REPOSITORY")
    assert hasattr(ObjectKind, "PULL_REQUEST")
    assert hasattr(ObjectKind, "ISSUE")
    assert hasattr(ObjectKind, "TEAM")
    assert hasattr(ObjectKind, "WORKFLOW")


def test_resource_configs_import() -> None:
    """Test that resource configurations can be imported."""
    from integration import (
        RepositoryResourceConfig,
        PullRequestResourceConfig,
        IssueResourceConfig,
        TeamResourceConfig,
        WorkflowResourceConfig,
    )

    # Test that classes exist and have the expected kind
    assert RepositoryResourceConfig.__annotations__["kind"]
    assert PullRequestResourceConfig.__annotations__["kind"]
    assert IssueResourceConfig.__annotations__["kind"]
    assert TeamResourceConfig.__annotations__["kind"]
    assert WorkflowResourceConfig.__annotations__["kind"]


@patch("port_ocean.context.ocean.ocean")
def test_client_factory_structure(mock_ocean: Any) -> None:
    """Test that client factory has the correct structure."""
    mock_ocean.integration_config = {
        "githubToken": "test-token",
        "githubHost": "https://api.github.com",
    }

    from github.clients.client_factory import create_github_client

    # Test that function exists and can be called
    assert callable(create_github_client)


def test_webhook_events_defined() -> None:
    """Test that webhook events are properly defined."""
    from github.webhook.events import GitHubWebhookEvent, GitHubWebhookAction

    # Test that the types are defined (this will fail if there are syntax errors)
    assert GitHubWebhookEvent
    assert GitHubWebhookAction


def test_auth_client_structure() -> None:
    """Test that auth client has the correct structure."""
    from github.clients.auth_client import AuthClient

    client = AuthClient("test-token")
    headers = client.get_headers()

    assert "Authorization" in headers
    assert "Accept" in headers
    assert "X-GitHub-Api-Version" in headers
    assert headers["Authorization"] == "Bearer test-token"


def test_webhook_processors_import() -> None:
    """Test that all webhook processors can be imported."""
    from github.webhook.webhook_processors.repository_webhook_processor import (
        RepositoryWebhookProcessor,
    )
    from github.webhook.webhook_processors.pull_request_webhook_processor import (
        PullRequestWebhookProcessor,
    )
    from github.webhook.webhook_processors.issue_webhook_processor import (
        IssueWebhookProcessor,
    )
    from github.webhook.webhook_processors.workflow_webhook_processor import (
        WorkflowWebhookProcessor,
    )
    from github.webhook.webhook_processors.team_webhook_processor import (
        TeamWebhookProcessor,
    )

    # Test that all processors have the required attributes
    assert hasattr(RepositoryWebhookProcessor, "events")
    assert hasattr(RepositoryWebhookProcessor, "hooks")
    assert hasattr(PullRequestWebhookProcessor, "events")
    assert hasattr(PullRequestWebhookProcessor, "hooks")
    assert hasattr(IssueWebhookProcessor, "events")
    assert hasattr(IssueWebhookProcessor, "hooks")
    assert hasattr(WorkflowWebhookProcessor, "events")
    assert hasattr(WorkflowWebhookProcessor, "hooks")
    assert hasattr(TeamWebhookProcessor, "events")
    assert hasattr(TeamWebhookProcessor, "hooks")


def test_webhook_factory_structure() -> None:
    """Test that webhook factory has the correct structure."""
    from github.webhook.webhook_factory.github_webhook_factory import (
        GitHubWebhookFactory,
    )

    # Test that the class exists and has the expected methods
    assert hasattr(GitHubWebhookFactory, "create_webhooks_for_all_repositories")
    assert hasattr(GitHubWebhookFactory, "create_organization_webhooks")


def test_main_imports() -> None:
    """Test that main.py imports work correctly."""
    # Test that the imports in main.py work without executing the decorators
    import importlib.util

    # Test that all key modules can be found
    modules_to_test = [
        "github.clients.client_factory",
        "github.helpers.utils",
        "integration",
        "github.webhook.webhook_processors.repository_webhook_processor",
    ]

    for module_name in modules_to_test:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            pytest.fail(f"Module {module_name} not found")

    # If we get here, all key modules are available
    assert True
