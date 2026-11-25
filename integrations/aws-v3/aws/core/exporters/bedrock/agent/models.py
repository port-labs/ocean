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
    description: str | None = None
    foundationModel: str | None = None
    idleSessionTTLInSeconds: int | None = None
    agentResourceRoleArn: str | None = None
    customerEncryptionKeyArn: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None
    preparedAt: str | None = None
    failureReasons: list[str] | None = None
    recommendedActions: list[str] | None = None
    instruction: str | None = None
    tags: dict[str, str] | None = None


class Agent(ResourceModel[AgentProperties]):
    Type: str = "AWS::Bedrock::Agent"
    Properties: AgentProperties = Field(default_factory=AgentProperties)


class SingleAgentRequest(ResourceRequestModel):
    agent_id: str = Field(..., description="The ID of the Bedrock Agent to export")


class PaginatedAgentRequest(ResourceRequestModel):
    pass
