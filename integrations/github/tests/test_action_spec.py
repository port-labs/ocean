import json
import re
from pathlib import Path

NUMERIC_OR_TEMPLATE_INPUTS = {
    "create_issue.milestone",
    "edit_issue.issueNumber",
    "edit_issue.milestone",
    "close_issue.issueNumber",
    "close_issue.duplicateIssueId",
    "update_pull_request.prNumber",
    "close_pull_request.prNumber",
    "merge_pull_request.prNumber",
    "review_pull_request.prNumber",
}
NUMERIC_OR_TEMPLATE_PATTERN = r"^(?:\d+|\{\{.+\}\})$"


def _action_inputs() -> dict[str, dict[str, object]]:
    spec_path = Path(__file__).parents[1] / ".port" / "spec.json"
    spec = json.loads(spec_path.read_text())
    return {
        f"{action['name']}.{input_['name']}": input_
        for action in spec["actions"]
        for input_ in action["inputs"]
    }


def test_action_inputs_do_not_use_number_validation() -> None:
    number_inputs = [
        name for name, input_ in _action_inputs().items() if input_["type"] == "number"
    ]

    assert number_inputs == []


def test_numeric_action_inputs_accept_only_numbers_or_templates() -> None:
    inputs = _action_inputs()

    for name in NUMERIC_OR_TEMPLATE_INPUTS:
        field = inputs[name]
        assert field["type"] == "string"
        assert field["pattern"] == NUMERIC_OR_TEMPLATE_PATTERN

        pattern = re.compile(str(field["pattern"]))
        assert pattern.fullmatch("42")
        assert pattern.fullmatch("{{ .inputs.prNumber }}")
        assert pattern.fullmatch("a123bc") is None
