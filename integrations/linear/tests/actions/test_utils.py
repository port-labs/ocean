import pytest

from linear.actions.types import CreateIssuePayload, UpdateIssuePayload
from linear.helpers.exceptions import MissingExecutionPropertyError


def test_create_issue_payload_keeps_priority_label() -> None:
    action_payload = CreateIssuePayload.from_execution_properties(
        {"title": "Bug", "teamId": "team-1", "priority": "High"}
    )

    assert action_payload.to_payload() == {
        "title": "Bug",
        "teamId": "team-1",
        "priority": "High",
    }
    assert action_payload.to_mutation().model_dump(exclude_none=True) == {
        "title": "Bug",
        "teamId": "team-1",
        "priority": 2,
    }


def test_update_issue_payload_preserves_empty_label_list() -> None:
    payload = UpdateIssuePayload.from_execution_properties(
        {"issueId": "ENG-1", "labelIds": []}
    ).to_payload()

    assert payload == {"labelIds": []}


def test_issue_payloads_ignore_undeclared_fields() -> None:
    properties = {
        "title": "Bug",
        "teamId": "team-1",
        "parentId": "ENG-1",
        "estimate": 3,
        "dueDate": "2026-09-10",
    }

    assert CreateIssuePayload.from_execution_properties(properties).to_payload() == {
        "title": "Bug",
        "teamId": "team-1",
    }
    assert UpdateIssuePayload.from_execution_properties(
        {**properties, "issueId": "ENG-1"}
    ).to_payload() == {"title": "Bug"}


@pytest.mark.parametrize("priority", ["high", "2", "Critical"])
def test_issue_payloads_reject_invalid_priority(priority: str) -> None:
    with pytest.raises(MissingExecutionPropertyError, match="priority"):
        UpdateIssuePayload.from_execution_properties(
            {"issueId": "ENG-1", "priority": priority}
        )
