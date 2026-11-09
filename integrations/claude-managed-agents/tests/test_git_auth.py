from __future__ import annotations

import pytest

from claude_managed_agents.actions.exceptions import InvalidActionParametersException
from claude_managed_agents.actions.trigger_agent_executor import TriggerAgentInputs


def test_trigger_agent_inputs_accepts_git_access_token() -> None:
    inputs = TriggerAgentInputs.model_validate(
        {
            "agentId": "a1",
            "prompt": "go",
            "environmentId": "e1",
            "gitAccessToken": "ghp_x",
        }
    )
    assert inputs.gitAccessToken == "ghp_x"


def test_trigger_agent_inputs_allows_git_fields_without_token() -> None:
    inputs = TriggerAgentInputs.model_validate(
        {
            "agentId": "a1",
            "prompt": "go",
            "environmentId": "e1",
            "gitProvider": "github",
            "gitAuthMethod": "bearerToken",
        }
    )
    assert inputs.gitAccessToken is None


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
