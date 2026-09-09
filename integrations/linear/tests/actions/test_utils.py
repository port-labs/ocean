import pytest

from linear.actions.utils import build_issue_create_input, build_issue_update_input
from linear.helpers.exceptions import MissingExecutionPropertyError


def test_build_issue_create_input_normalizes_priority() -> None:
    assert build_issue_create_input(
        {"title": "Bug", "teamId": "team-1", "priority": "2"}
    ) == {"title": "Bug", "teamId": "team-1", "priority": 2}


def test_build_issue_update_input_preserves_empty_label_list() -> None:
    assert build_issue_update_input({"labelIds": []}) == {"labelIds": []}


def test_issue_inputs_ignore_undeclared_fields() -> None:
    properties = {
        "title": "Bug",
        "parentId": "ENG-1",
        "estimate": 3,
        "dueDate": "2026-09-10",
    }

    assert build_issue_create_input(properties) == {"title": "Bug"}
    assert build_issue_update_input(properties) == {"title": "Bug"}


@pytest.mark.parametrize("priority", ["high", "-1", "5"])
def test_issue_inputs_reject_invalid_priority(priority: str) -> None:
    with pytest.raises(MissingExecutionPropertyError, match="priority"):
        build_issue_update_input({"priority": priority})
