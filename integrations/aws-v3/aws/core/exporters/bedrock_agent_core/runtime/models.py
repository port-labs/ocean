from typing import TypedDict

from pydantic import Field, ConfigDict

from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class AgentRuntimeRecord(TypedDict, total=False):
    """Shape of an item returned by list_agent_runtimes and get_agent_runtime."""

    agentRuntimeId: str
    agentRuntimeArn: str
    agentRuntimeName: str
    agentRuntimeVersion: str
    description: str
    status: str
    lastUpdatedAt: str
    createdAt: str
    roleArn: str
    networkConfiguration: dict
    lifecycleConfiguration: dict
    metadataConfiguration: dict
    agentRuntimeArtifact: dict
    platformVersion: str


class BedrockAgentCoreRuntimeProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="ignore")

    agentRuntimeId: str = Field(default_factory=str)
    agentRuntimeArn: str = Field(default_factory=str)
    agentRuntimeName: str = Field(default_factory=str)
    agentRuntimeVersion: str | None = None
    description: str | None = None
    status: str | None = None
    lastUpdatedAt: str | None = None
    createdAt: str | None = None
    roleArn: str | None = None
    networkConfiguration: dict | None = None
    lifecycleConfiguration: dict | None = None
    metadataConfiguration: dict | None = None
    agentRuntimeArtifact: dict | None = None
    platformVersion: str | None = None


class BedrockAgentCoreRuntime(ResourceModel[BedrockAgentCoreRuntimeProperties]):
    Type: str = "AWS::BedrockAgentCore::Runtime"
    Properties: BedrockAgentCoreRuntimeProperties = Field(
        default_factory=BedrockAgentCoreRuntimeProperties
    )


class SingleBedrockAgentCoreRuntimeRequest(ResourceRequestModel):
    """Options for exporting a single BedrockAgentCore Runtime."""

    agent_runtime_id: str = Field(
        ..., description="The ID of the BedrockAgentCore Runtime to export"
    )


class PaginatedBedrockAgentCoreRuntimeRequest(ResourceRequestModel):
    """Options for exporting all BedrockAgentCore Runtimes in a region."""

    pass
