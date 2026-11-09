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


def test_trigger_agent_inputs_rejects_empty_git_access_token() -> None:
    with pytest.raises(InvalidActionParametersException, match="gitAccessToken"):
        TriggerAgentInputs.from_execution_properties(
            {
                "agentId": "a1",
                "prompt": "go",
                "environmentId": "e1",
                "gitAccessToken": "",
            }
        )
