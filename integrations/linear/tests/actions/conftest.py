"""Shared fixtures for Linear action executor tests."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.models import (
    WorkflowIntegrationActionConfig,
    WorkflowNodeRun,
    WorkflowNodeRunStatus,
)

from linear.core.mutations.document.types import MutationDocument
from linear.core.mutations.issue.types import MutationComment, MutationIssue
from linear.core.mutations.reaction.types import MutationReaction


def make_run(action_name: str, execution_properties: dict[str, Any]) -> WorkflowNodeRun:
    return WorkflowNodeRun(
        id="run-1",
        status=WorkflowNodeRunStatus.IN_PROGRESS,
        config=WorkflowIntegrationActionConfig(
            type="INTEGRATION_ACTION",
            installationId="test-installation-id",
            integrationProvider="linear",
            integrationInvocationType=action_name,
            integrationActionExecutionProperties=execution_properties,
        ),
    )


@pytest.fixture
def mock_port_client() -> MagicMock:
    client = MagicMock()
    client.update_run_started = AsyncMock()
    client.report_run_completed = AsyncMock()
    client.post_run_log = AsyncMock()
    return client


@pytest.fixture
def mock_linear_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_issue_mutations() -> MagicMock:
    mutations = MagicMock()
    mutations.create_issue = AsyncMock(
        return_value=MutationIssue(
            id="issue-1",
            identifier="ENG-1",
            title="Test issue",
            url="https://linear.app/test/issue/ENG-1",
        )
    )
    mutations.update_issue = AsyncMock(
        return_value=MutationIssue(
            id="issue-1",
            identifier="ENG-1",
            title="Updated issue",
            url="https://linear.app/test/issue/ENG-1",
        )
    )
    mutations.create_comment = AsyncMock(
        return_value=MutationComment(
            id="comment-1",
            body="Hello",
            createdAt="2026-01-01",
        )
    )
    mutations.archive_issue = AsyncMock(return_value=None)
    mutations.delete_issue = AsyncMock(return_value=None)
    return mutations


@pytest.fixture
def mock_document_mutations() -> MagicMock:
    mutations = MagicMock()
    mutations.create_document = AsyncMock(
        return_value=MutationDocument(
            id="doc-1",
            title="Notes",
            url="https://linear.app/test/document/doc-1",
        )
    )
    return mutations


@pytest.fixture
def mock_reaction_mutations() -> MagicMock:
    mutations = MagicMock()
    mutations.create_reaction = AsyncMock(
        return_value=MutationReaction(id="reaction-1", emoji="+1")
    )
    return mutations


@pytest.fixture
def mock_issue_exporter() -> MagicMock:
    exporter = MagicMock()
    exporter.get_resource = AsyncMock(
        return_value={"team": {"id": "team-1", "name": "Engineering", "key": "ENG"}}
    )
    return exporter


def create_executor(executor_cls: type[Any], mock_linear_client: MagicMock) -> Any:
    with patch(
        "linear.actions.abstract_linear_executor.LinearClient.create_from_ocean_configuration",
        return_value=mock_linear_client,
    ):
        executor = executor_cls()
    executor.client = mock_linear_client
    return executor
