from azure_integration.foundry.helpers.invoke_mode import invoke_agent_completion_mode


def test_invoke_agent_completion_mode_report_false() -> None:
    assert invoke_agent_completion_mode(report_invocation_status=False) is False


def test_invoke_agent_completion_mode_report_true() -> None:
    assert invoke_agent_completion_mode(report_invocation_status=True) is True
