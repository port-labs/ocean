from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class ProjectArtifacts(BaseModel):
    type: Optional[str] = None
    location: Optional[str] = None
    path: Optional[str] = None
    namespaceType: Optional[str] = None
    name: Optional[str] = None
    packaging: Optional[str] = None
    overrideArtifactName: Optional[bool] = None
    encryptionDisabled: Optional[bool] = None
    artifactIdentifier: Optional[str] = None
    bucketOwnerAccess: Optional[str] = None

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class ProjectEnvironment(BaseModel):
    type: Optional[str] = None
    image: Optional[str] = None
    computeType: Optional[str] = None
    environmentVariables: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    privilegedMode: Optional[bool] = None
    certificate: Optional[str] = None
    registryCredential: Optional[Dict[str, Any]] = None
    imagePullCredentialsType: Optional[str] = None

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class ProjectSource(BaseModel):
    type: Optional[str] = None
    location: Optional[str] = None
    gitCloneDepth: Optional[int] = None
    gitSubmodulesConfig: Optional[Dict[str, Any]] = None
    buildspec: Optional[str] = None
    auth: Optional[Dict[str, Any]] = None
    reportBuildStatus: Optional[bool] = None
    buildStatusConfig: Optional[Dict[str, Any]] = None
    insecureSsl: Optional[bool] = None
    sourceIdentifier: Optional[str] = None

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class ProjectVpcConfig(BaseModel):
    vpcId: Optional[str] = None
    subnets: Optional[List[str]] = Field(default_factory=list)
    securityGroupIds: Optional[List[str]] = Field(default_factory=list)

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class ProjectProperties(BaseModel):
    name: str = Field(default_factory=str)
    arn: str = Field(default_factory=str)
    description: Optional[str] = None
    source: Optional[ProjectSource] = None
    secondarySources: Optional[List[ProjectSource]] = Field(default_factory=list)
    sourceVersion: Optional[str] = None
    secondarySourceVersions: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    artifacts: Optional[ProjectArtifacts] = None
    secondaryArtifacts: Optional[List[ProjectArtifacts]] = Field(default_factory=list)
    cache: Optional[Dict[str, Any]] = None
    environment: Optional[ProjectEnvironment] = None
    serviceRole: Optional[str] = None
    timeoutInMinutes: Optional[int] = None
    queuedTimeoutInMinutes: Optional[int] = None
    encryptionKey: Optional[str] = None
    tags: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    vpcConfig: Optional[ProjectVpcConfig] = None
    badge: Optional[Dict[str, Any]] = None
    logsConfig: Optional[Dict[str, Any]] = None
    fileSystemLocations: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    buildBatchConfig: Optional[Dict[str, Any]] = None
    concurrentBuildLimit: Optional[int] = None
    projectVisibility: Optional[str] = None
    publicReadOnlyAccess: Optional[bool] = None
    resourceAccessRole: Optional[str] = None
    created: Optional[str] = None
    lastModified: Optional[str] = None
    webhook: Optional[Dict[str, Any]] = None

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True


class CodeBuildProject(ResourceModel[ProjectProperties]):
    Type: str = "AWS::CodeBuild::Project"
    Properties: ProjectProperties = Field(default_factory=ProjectProperties)


class SingleCodeBuildProjectRequest(ResourceRequestModel):
    """Options for exporting a single CodeBuild project."""
    
    project_name: str = Field(..., description="The name of the CodeBuild project to export")


class PaginatedCodeBuildProjectRequest(ResourceRequestModel):
    """Options for exporting all CodeBuild projects in a region."""
    
    pass