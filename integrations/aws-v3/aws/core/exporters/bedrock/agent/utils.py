from aws.utils import RegionHelper


def build_agent_arn(region: str, account_id: str, agent_id: str) -> str:
    """Build a Bedrock agent ARN in the integration's partition (aws, aws-cn, aws-us-gov)."""
    partition = RegionHelper.get_partition()
    return f"arn:{partition}:bedrock:{region}:{account_id}:agent/{agent_id}"
