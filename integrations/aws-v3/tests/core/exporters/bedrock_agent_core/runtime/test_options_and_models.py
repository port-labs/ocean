from datetime import datetime, timezone

from aws.core.exporters.bedrock_agent_core.runtime.models import (
    BedrockAgentCoreRuntime,
    BedrockAgentCoreRuntimeProperties,
    PaginatedBedrockAgentCoreRuntimeRequest,
    SingleBedrockAgentCoreRuntimeRequest,
)
from aws.core.exporters.bedrock_agent_core.runtime.regions import (
    BEDROCK_AGENT_CORE_RUNTIME_SUPPORTED_REGIONS,
)
from aws_integration.overrides import AWSBedrockAgentCoreRuntimeResourceConfig


def test_model_type_and_defaults() -> None:
    model = BedrockAgentCoreRuntime()

    assert model.Type == "AWS::BedrockAgentCore::Runtime"
    assert model.Properties.agentRuntimeId == ""
    assert model.Properties.tags is None


def test_properties_accept_aws_datetimes_and_dump_pascal_case() -> None:
    properties = BedrockAgentCoreRuntimeProperties(
        agentRuntimeId="rt-1",
        agentRuntimeName="my-runtime",
        createdAt=datetime(2026, 5, 15, 9, 30, tzinfo=timezone.utc),
    )

    dumped = properties.model_dump(mode="json", by_alias=True, exclude_unset=True)

    assert dumped == {
        "AgentRuntimeId": "rt-1",
        "AgentRuntimeName": "my-runtime",
        "CreatedAt": "2026-05-15T09:30:00Z",
    }


def test_environment_variables_are_dropped() -> None:
    properties = BedrockAgentCoreRuntimeProperties.model_validate(
        {
            "agentRuntimeId": "rt-1",
            "environmentVariables": {"OPENAI_API_KEY": "sk-SECRET"},
        }
    )

    dumped = properties.model_dump(by_alias=True)

    assert "EnvironmentVariables" not in dumped
    assert "sk-SECRET" not in str(dumped)


def test_request_models() -> None:
    single = SingleBedrockAgentCoreRuntimeRequest(
        agent_runtime_id="rt-1", region="us-east-1", account_id="123456789012"
    )
    paginated = PaginatedBedrockAgentCoreRuntimeRequest(
        region="us-east-1",
        account_id="123456789012",
        include=["ListAgentRuntimeTagsAction"],
    )

    assert single.agent_runtime_id == "rt-1"
    assert paginated.include == ["ListAgentRuntimeTagsAction"]


def test_supported_regions_match_aws_docs() -> None:
    # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html
    assert len(BEDROCK_AGENT_CORE_RUNTIME_SUPPORTED_REGIONS) == 24
    assert {"us-gov-west-1", "cn-north-1", "ap-southeast-5"} <= (
        BEDROCK_AGENT_CORE_RUNTIME_SUPPORTED_REGIONS
    )


def test_probe_permissions_use_agentcore_iam_prefix() -> None:
    assert AWSBedrockAgentCoreRuntimeResourceConfig.probe_permissions == (
        "bedrock-agentcore:ListAgentRuntimes",
        "bedrock-agentcore:GetAgentRuntime",
    )
