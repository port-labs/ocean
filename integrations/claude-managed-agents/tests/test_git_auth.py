from __future__ import annotations

import pytest

from claude_managed_agents.actions.exceptions import InvalidActionParametersException
from claude_managed_agents.actions.git_auth import resolve_git_auth
from claude_managed_agents.actions.trigger_agent_executor import TriggerAgentInputs


def test_trigger_agent_inputs_resolves_git_access_from_token() -> None:
    inputs = TriggerAgentInputs.model_validate(
        {
            "agentId": "a1",
            "prompt": "go",
            "environmentId": "e1",
            "gitAccessToken": "ghp_x",
        }
    )
    assert inputs.git_access is not None
    assert inputs.git_access.mount_token == "ghp_x"


def test_trigger_agent_inputs_ignores_git_fields_without_token() -> None:
    inputs = TriggerAgentInputs.model_validate(
        {
            "agentId": "a1",
            "prompt": "go",
            "environmentId": "e1",
            "gitProvider": "github",
            "gitAuthMethod": "bearerToken",
        }
    )
    assert inputs.git_access is None


@pytest.mark.parametrize(
    ("execution_properties", "match"),
    [
        ({"gitProvider": "gitlab"}, "gitProvider"),
        ({"gitAuthMethod": "github_app"}, "gitAuthMethod"),
        ({"gitAccessToken": ""}, "gitAccessToken"),
    ],
)
def test_trigger_agent_inputs_rejects_invalid_git_auth(
    execution_properties: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(InvalidActionParametersException, match=match):
        TriggerAgentInputs.from_execution_properties(
            {
                "agentId": "a1",
                "prompt": "go",
                "environmentId": "e1",
                **execution_properties,
            }
        )


def test_resolve_git_auth() -> None:
    resolved = resolve_git_auth("ghp_test")
    assert resolved.mount_token == "ghp_test"
