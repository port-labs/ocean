# Regions where Amazon Bedrock AgentCore Runtime is available, from
# https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html
# Other regions have no bedrock-agentcore-control endpoint, so calls there fail
# with a connection error instead of an access-denied error; filter them out up front.
BEDROCK_AGENT_CORE_RUNTIME_SUPPORTED_REGIONS: frozenset[str] = frozenset(
    {
        "us-east-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
        "ca-central-1",
        "sa-east-1",
        "eu-central-1",
        "eu-west-1",
        "eu-west-2",
        "eu-west-3",
        "eu-north-1",
        "eu-south-1",
        "eu-south-2",
        "ap-south-1",
        "ap-south-2",
        "ap-southeast-1",
        "ap-southeast-2",
        "ap-southeast-5",
        "ap-southeast-7",
        "ap-northeast-1",
        "ap-northeast-2",
        "us-gov-west-1",
        "cn-north-1",
        "cn-northwest-1",
    }
)
