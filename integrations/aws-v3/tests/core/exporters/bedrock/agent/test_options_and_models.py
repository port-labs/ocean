from datetime import datetime, timezone
from unittest.mock import patch

from aws.core.exporters.bedrock.agent.models import (
    Agent,
    AgentProperties,
    PaginatedAgentRequest,
    SingleAgentRequest,
)
from aws.core.exporters.bedrock.agent.regions import BEDROCK_AGENT_SUPPORTED_REGIONS
from aws.core.exporters.bedrock.agent.utils import build_agent_arn


def test_model_type_and_defaults() -> None:
    model = Agent()

    assert model.Type == "AWS::Bedrock::Agent"
    assert model.Properties.agentId == ""
    assert model.Properties.tags is None


def test_properties_accept_aws_datetimes_and_dump_pascal_case() -> None:
    properties = AgentProperties(
        agentId="ABCDEF1234",
        agentName="my-agent",
        createdAt=datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
    )

    dumped = properties.model_dump(mode="json", by_alias=True, exclude_unset=True)

    assert dumped == {
        "AgentId": "ABCDEF1234",
        "AgentName": "my-agent",
        "CreatedAt": "2024-01-15T10:30:00Z",
    }


def test_prompt_fields_are_dropped() -> None:
    properties = AgentProperties.model_validate(
        {
            "agentId": "ABCDEF1234",
            "instruction": "secret prompt",
            "promptOverrideConfiguration": {"promptConfigurations": []},
        }
    )

    dumped = properties.model_dump(by_alias=True)

    assert "Instruction" not in dumped
    assert "PromptOverrideConfiguration" not in dumped


def test_request_models() -> None:
    single = SingleAgentRequest(
        agent_id="ABCDEF1234", region="us-east-1", account_id="123456789012", include=[]
    )
    paginated = PaginatedAgentRequest(
        region="us-east-1", account_id="123456789012", include=["ListAgentTagsAction"]
    )

    assert single.agent_id == "ABCDEF1234"
    assert paginated.include == ["ListAgentTagsAction"]


def test_supported_regions_match_aws_docs() -> None:
    # https://docs.aws.amazon.com/bedrock/latest/userguide/agents-supported.html
    assert len(BEDROCK_AGENT_SUPPORTED_REGIONS) == 16
    assert "eu-central-2" in BEDROCK_AGENT_SUPPORTED_REGIONS
    assert "us-gov-west-1" in BEDROCK_AGENT_SUPPORTED_REGIONS


@patch(
    "aws.core.exporters.bedrock.agent.utils.RegionHelper.get_partition",
    return_value="aws-us-gov",
)
def test_agent_arn_uses_integration_partition(_: object) -> None:
    assert (
        build_agent_arn("us-gov-west-1", "123456789012", "ABCDEF1234")
        == "arn:aws-us-gov:bedrock:us-gov-west-1:123456789012:agent/ABCDEF1234"
    )
