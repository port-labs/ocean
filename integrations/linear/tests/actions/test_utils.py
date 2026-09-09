import pytest

from linear.actions.create_issue_executor import CreateIssueInput
from linear.actions.update_issue_executor import UpdateIssueInput
from linear.helpers.exceptions import MissingExecutionPropertyError


def test_create_issue_input_normalizes_priority() -> None:
    payload = CreateIssueInput.from_execution_properties(
        {"title": "Bug", "teamId": "team-1", "priority": "2"}
    ).to_api_payload()

    assert payload == {"title": "Bug", "teamId": "team-1", "priority": 2}


def test_update_issue_input_preserves_empty_label_list() -> None:
    payload = UpdateIssueInput.from_execution_properties(
        {"issueId": "ENG-1", "labelIds": []}
    ).to_api_payload()

    assert payload == {"labelIds": []}


def test_issue_inputs_ignore_undeclared_fields() -> None:
    properties = {
        "title": "Bug",
        "teamId": "team-1",
        "parentId": "ENG-1",
        "estimate": 3,
        "dueDate": "2026-09-10",
    }

    assert CreateIssueInput.from_execution_properties(properties).to_api_payload() == {
        "title": "Bug",
        "teamId": "team-1",
    }
    assert UpdateIssueInput.from_execution_properties(
        {**properties, "issueId": "ENG-1"}
    ).to_api_payload() == {"title": "Bug"}


@pytest.mark.parametrize("priority", ["high", "-1", "5"])
def test_issue_inputs_reject_invalid_priority(priority: str) -> None:
    with pytest.raises(MissingExecutionPropertyError, match="priority"):
        UpdateIssueInput.from_execution_properties(
            {"issueId": "ENG-1", "priority": priority}
        )
