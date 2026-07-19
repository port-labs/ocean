from typing import Any
from pydantic import Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel, BaseAWSPropertiesModel


class LambdaFunctionProperties(BaseAWSPropertiesModel):
    Architectures: list[str] = Field(default_factory=list)
    CodeSha256: str = Field(default_factory=str)
    CodeSize: int = Field(default=0)
    DeadLetterConfig: dict[str, Any] | None = None
    Description: str = Field(default_factory=str)
    Environment: dict[str, Any] | None = None
    EphemeralStorage: dict[str, Any] | None = None
    FileSystemConfigs: list[dict[str, Any]] = Field(default_factory=list)
    FunctionArn: str = Field(default_factory=str)
    FunctionName: str = Field(default_factory=str)
    Handler: str = Field(default_factory=str)
    ImageConfigResponse: dict[str, Any] | None = None
    KmsKeyArn: str | None = Field(default=None, alias="KMSKeyArn")
    LastModified: str = Field(default_factory=str)
    LastUpdateStatus: str = Field(default_factory=str)
    LastUpdateStatusReason: str = Field(default_factory=str)
    LastUpdateStatusReasonCode: str = Field(default_factory=str)
    Layers: list[dict[str, Any]] = Field(default_factory=list)
    LoggingConfig: dict[str, Any] | None = None
    MasterArn: str | None = None
    MemorySize: int = Field(default=128)
    PackageType: str = Field(default="Zip")
    RevisionId: str = Field(default_factory=str)
    Role: str = Field(default_factory=str)
    Runtime: str = Field(default_factory=str)
    RuntimeVersionConfig: dict[str, Any] | None = None
    SigningJobArn: str | None = None
    SigningProfileVersionArn: str | None = None
    SnapStart: dict[str, Any] | None = None
    State: str = Field(default_factory=str)
    StateReason: str | None = None
    StateReasonCode: str | None = None
    Tags: dict[str, Any] = Field(default_factory=dict)
    Timeout: int = Field(default=3)
    TracingConfig: dict[str, Any] | None = None
    Version: str = Field(default_factory=str)
    VpcConfig: dict[str, Any] | None = None


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
