from typing import Optional, Any
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class LambdaFunctionProperties(BaseModel):
    Architectures: list[str] = Field(default_factory=list)
    CodeSha256: str = Field(default_factory=str)
    CodeSize: int = Field(default=0)
    DeadLetterConfig: Optional[dict[str, Any]] = None
    Description: str = Field(default_factory=str)
    Environment: Optional[dict[str, Any]] = None
    EphemeralStorage: Optional[dict[str, Any]] = None
    FileSystemConfigs: list[dict[str, Any]] = Field(default_factory=list)
    FunctionArn: str = Field(default_factory=str)
    FunctionName: str = Field(default_factory=str)
    Handler: str = Field(default_factory=str)
    ImageConfigResponse: Optional[dict[str, Any]] = None
    KmsKeyArn: Optional[str] = Field(default=None, alias="KMSKeyArn")
    LastModified: str = Field(default_factory=str)
    LastUpdateStatus: str = Field(default_factory=str)
    LastUpdateStatusReason: str = Field(default_factory=str)
    LastUpdateStatusReasonCode: str = Field(default_factory=str)
    Layers: list[dict[str, Any]] = Field(default_factory=list)
    LoggingConfig: Optional[dict[str, Any]] = None
    MasterArn: Optional[str] = None
    MemorySize: int = Field(default=128)
    PackageType: str = Field(default="Zip")
    RevisionId: str = Field(default_factory=str)
    Role: str = Field(default_factory=str)
    Runtime: str = Field(default_factory=str)
    RuntimeVersionConfig: Optional[dict[str, Any]] = None
    SigningJobArn: Optional[str] = None
    SigningProfileVersionArn: Optional[str] = None
    SnapStart: Optional[dict[str, Any]] = None
    State: str = Field(default_factory=str)
    StateReason: Optional[str] = None
    StateReasonCode: Optional[str] = None
    Tags: dict[str, Any] = Field(default_factory=dict)
    Timeout: int = Field(default=3)
    TracingConfig: Optional[dict[str, Any]] = None
    Version: str = Field(default_factory=str)
    VpcConfig: Optional[dict[str, Any]] = None

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"


class LambdaFunction(ResourceModel[LambdaFunctionProperties]):
    Type: str = "AWS::Lambda::Function"
    Properties: LambdaFunctionProperties = Field(
        default_factory=LambdaFunctionProperties
    )


class SingleLambdaFunctionRequest(ResourceRequestModel):
    """Options for exporting a single Lambda function."""

    function_name: str = Field(
        ..., description="The name of the Lambda function to export"
    )


class PaginatedLambdaFunctionRequest(ResourceRequestModel):
    """Options for exporting all Lambda functions in a region."""

    pass
