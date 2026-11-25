from datetime import datetime
from typing import Any

from pydantic import Field

from aws.core.modeling.resource_models import (
    BaseAWSPropertiesModel,
    ResourceModel,
    ResourceRequestModel,
)


class AgentProperties(BaseAWSPropertiesModel):
    """Bedrock agent properties exported to Port.

    The agent's prompt (``instruction``, ``promptOverrideConfiguration``) is
    intentionally not declared: ``BaseAWSPropertiesModel`` ignores undeclared
    fields, so it never leaves the integration.
    """

    agentId: str = Field(default_factory=str, alias="AgentId")
    agentName: str = Field(default_factory=str, alias="AgentName")
    agentArn: str = Field(default_factory=str, alias="AgentArn")
    agentStatus: str | None = Field(default=None, alias="AgentStatus")
    agentVersion: str | None = Field(default=None, alias="AgentVersion")
    latestAgentVersion: str | None = Field(default=None, alias="LatestAgentVersion")
    description: str | None = Field(default=None, alias="Description")
    foundationModel: str | None = Field(default=None, alias="FoundationModel")
    orchestrationType: str | None = Field(default=None, alias="OrchestrationType")
    idleSessionTTLInSeconds: int | None = Field(
        default=None, alias="IdleSessionTTLInSeconds"
    )
    agentResourceRoleArn: str | None = Field(default=None, alias="AgentResourceRoleArn")
    customerEncryptionKeyArn: str | None = Field(
        default=None, alias="CustomerEncryptionKeyArn"
    )
    guardrailConfiguration: dict[str, Any] | None = Field(
        default=None, alias="GuardrailConfiguration"
    )
    memoryConfiguration: dict[str, Any] | None = Field(
        default=None, alias="MemoryConfiguration"
    )
    agentCollaboration: str | None = Field(default=None, alias="AgentCollaboration")
    createdAt: datetime | None = Field(default=None, alias="CreatedAt")
    updatedAt: datetime | None = Field(default=None, alias="UpdatedAt")
    preparedAt: datetime | None = Field(default=None, alias="PreparedAt")
    failureReasons: list[str] | None = Field(default=None, alias="FailureReasons")
    recommendedActions: list[str] | None = Field(
        default=None, alias="RecommendedActions"
    )
    tags: dict[str, str] | None = Field(default=None, alias="Tags")


class Agent(ResourceModel[AgentProperties]):
    Type: str = "AWS::Bedrock::Agent"
    Properties: AgentProperties = Field(default_factory=AgentProperties)


class SingleAgentRequest(ResourceRequestModel):
    """Options for exporting a single Bedrock agent."""

    agent_id: str = Field(..., description="The ID of the Bedrock Agent to export")


class PaginatedAgentRequest(ResourceRequestModel):
    """Options for exporting all Bedrock agents in a region."""

    pass
