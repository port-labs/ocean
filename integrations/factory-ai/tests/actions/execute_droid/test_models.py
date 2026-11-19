from __future__ import annotations

import pytest

from factory_ai.actions.exceptions import InvalidActionParametersError
from factory_ai.actions.execute_droid.models import (
    ExecuteDroidComputerInputs,
    ExecuteDroidEnvironmentInputs,
    ExecuteDroidResponse,
    ExecuteDroidSessionInputs,
    parse_execute_droid_inputs,
)


class TestParseExecuteDroidInputs:
    def test_environment_target_builds_body(self) -> None:
        inputs = parse_execute_droid_inputs(
            {
                "prompt": "Fix the flaky test",
                "targetKind": "environment",
                "environmentId": "env-1",
                "model": "claude-sonnet",
                "reasoningEffort": "medium",
            }
        )
        assert isinstance(inputs, ExecuteDroidEnvironmentInputs)
        assert inputs.to_request_body() == {
            "prompt": "Fix the flaky test",
            "target": {"kind": "environment", "environmentId": "env-1"},
            "model": "claude-sonnet",
            "reasoningEffort": "medium",
        }

    def test_computer_target_builds_body(self) -> None:
        inputs = parse_execute_droid_inputs(
            {
                "prompt": "Ship it",
                "targetKind": "computer",
                "computerId": "comp-1",
            }
        )
        assert isinstance(inputs, ExecuteDroidComputerInputs)
        assert inputs.to_request_body() == {
            "prompt": "Ship it",
            "target": {"kind": "computer", "computerId": "comp-1"},
        }

    def test_session_target_builds_body(self) -> None:
        inputs = parse_execute_droid_inputs(
            {
                "prompt": "Continue",
                "targetKind": "session",
                "sessionId": "sess-1",
                # New-session fields are ignored for follow-ups.
                "model": "claude-sonnet",
                "reasoningEffort": "high",
            }
        )
        assert isinstance(inputs, ExecuteDroidSessionInputs)
        assert inputs.to_request_body() == {
            "prompt": "Continue",
            "target": {"kind": "session", "sessionId": "sess-1"},
        }

    def test_missing_prompt_raises(self) -> None:
        with pytest.raises(InvalidActionParametersError):
            parse_execute_droid_inputs(
                {"targetKind": "environment", "environmentId": "env-1"}
            )

    def test_environment_requires_environment_id(self) -> None:
        with pytest.raises(InvalidActionParametersError, match="environmentId"):
            parse_execute_droid_inputs({"prompt": "hi", "targetKind": "environment"})

    def test_computer_requires_computer_id(self) -> None:
        with pytest.raises(InvalidActionParametersError, match="computerId"):
            parse_execute_droid_inputs({"prompt": "hi", "targetKind": "computer"})

    def test_session_requires_session_id(self) -> None:
        with pytest.raises(InvalidActionParametersError, match="sessionId"):
            parse_execute_droid_inputs({"prompt": "hi", "targetKind": "session"})

    def test_unknown_target_kind_raises(self) -> None:
        with pytest.raises(InvalidActionParametersError):
            parse_execute_droid_inputs(
                {
                    "prompt": "hi",
                    "targetKind": "template",
                    "templateId": "tmpl-1",
                }
            )

    def test_invalid_reasoning_effort_raises(self) -> None:
        with pytest.raises(InvalidActionParametersError):
            parse_execute_droid_inputs(
                {
                    "prompt": "hi",
                    "targetKind": "environment",
                    "environmentId": "env-1",
                    "reasoningEffort": "extreme",
                }
            )


def test_execute_droid_response_parses_aliases() -> None:
    response = ExecuteDroidResponse.model_validate(
        {
            "sessionId": "sess-1",
            "computerId": "comp-1",
            "messageId": "msg-1",
        }
    )
    assert response.session_id == "sess-1"
    assert response.computer_id == "comp-1"
    assert response.message_id == "msg-1"
