from datetime import datetime
from typing import Any

from pydantic import Field

from aws.core.modeling.resource_models import (
    BaseAWSPropertiesModel,
    ResourceModel,
    ResourceRequestModel,
)


class BedrockAgentCoreRuntimeProperties(BaseAWSPropertiesModel):
    """AgentCore Runtime properties exported to Port.

    ``environmentVariables`` is intentionally not declared: it commonly holds
    secrets such as LLM API keys, and ``BaseAWSPropertiesModel`` ignores
    undeclared fields, so it never leaves the integration.
    """

    agentRuntimeId: str = Field(default_factory=str, alias="AgentRuntimeId")
    agentRuntimeArn: str = Field(default_factory=str, alias="AgentRuntimeArn")
    agentRuntimeName: str = Field(default_factory=str, alias="AgentRuntimeName")
    agentRuntimeVersion: str | None = Field(default=None, alias="AgentRuntimeVersion")
    description: str | None = Field(default=None, alias="Description")
    status: str | None = Field(default=None, alias="Status")
    roleArn: str | None = Field(default=None, alias="RoleArn")
    agentRuntimeArtifact: dict[str, Any] | None = Field(
        default=None, alias="AgentRuntimeArtifact"
    )
    networkConfiguration: dict[str, Any] | None = Field(
        default=None, alias="NetworkConfiguration"
    )
    protocolConfiguration: dict[str, Any] | None = Field(
        default=None, alias="ProtocolConfiguration"
    )
    authorizerConfiguration: dict[str, Any] | None = Field(
        default=None, alias="AuthorizerConfiguration"
    )
    lifecycleConfiguration: dict[str, Any] | None = Field(
        default=None, alias="LifecycleConfiguration"
    )
    workloadIdentityDetails: dict[str, Any] | None = Field(
        default=None, alias="WorkloadIdentityDetails"
    )
    createdAt: datetime | None = Field(default=None, alias="CreatedAt")
    lastUpdatedAt: datetime | None = Field(default=None, alias="LastUpdatedAt")
    tags: dict[str, str] | None = Field(default=None, alias="Tags")


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
