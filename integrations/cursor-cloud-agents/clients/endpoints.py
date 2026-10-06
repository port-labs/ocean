V0_AGENTS = "/v0/agents"
V1_AGENTS = "/v1/agents"


def v1_agent_runs(agent_id: str) -> str:
    return f"{V1_AGENTS}/{agent_id}/runs"


def v1_agent_run(agent_id: str, run_id: str) -> str:
    return f"{v1_agent_runs(agent_id)}/{run_id}"


def v1_agent_usage(agent_id: str) -> str:
    return f"{V1_AGENTS}/{agent_id}/usage"
