from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class AgentProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="ignore")

    agentId: str = Field(default_factory=str)
    agentName: str = Field(default_factory=str)
    agentArn: str | None = None
    agentStatus: str | None = None
    agentVersion: str | None = None
    agentResourceRoleArn: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None
    preparedAt: str | None = None
    description: str | None = None
    foundationModel: str | None = None
    idleSessionTTLInSeconds: int | None = None
    instruction: str | None = None
    customerEncryptionKeyArn: str | None = None
    agentCollaboration: str | None = None
    orchestrationType: str | None = None
    failureReasons: list[str] | None = None
    guardrailConfiguration: dict[str, str] | None = None
    memoryConfiguration: dict | None = None
    tags: dict[str, str] | None = None


class BedrockAgent(ResourceModel[AgentProperties]):
    Type: str = "AWS::Bedrock::Agent"
    Properties: AgentProperties = Field(default_factory=AgentProperties)


class SingleBedrockAgentRequest(ResourceRequestModel):
    """Options for exporting a single Bedrock Agent."""

    agent_id: str = Field(..., description="The ID of the Bedrock Agent to export")


class PaginatedBedrockAgentRequest(ResourceRequestModel):
    """Options for exporting all Bedrock Agents in a region."""

    pass
