from aws.utils import RegionHelper


def build_agent_runtime_arn(region: str, account_id: str, agent_runtime_id: str) -> str:
    """Build an AgentCore runtime ARN in the integration's partition."""
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:bedrock-agentcore:{region}:{account_id}:"
        f"runtime/{agent_runtime_id}"
    )
