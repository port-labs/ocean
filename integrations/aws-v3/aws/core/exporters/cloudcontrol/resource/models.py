from pydantic import ConfigDict, Field

from aws.core.exporters.cloudcontrol.resource.scope import CloudControlResourceScope
from aws.core.modeling.resource_models import (
    BaseAWSPropertiesModel,
    ResourceModel,
    ResourceRequestModel,
)


class CloudControlResourceProperties(BaseAWSPropertiesModel):
    """Cloud Control properties are type-specific CloudFormation documents."""

    model_config = ConfigDict(extra="allow")

    Identifier: str = Field(default_factory=str)


class CloudControlResource(ResourceModel[CloudControlResourceProperties]):
    Type: str = Field(default="")
    Properties: CloudControlResourceProperties = Field(
        default_factory=CloudControlResourceProperties
    )


class SingleCloudControlResourceRequest(ResourceRequestModel):
    type_name: str = Field(
        ...,
        description="CloudFormation type name to fetch, e.g. AWS::IAM::Role",
    )
    identifier: str = Field(
        ...,
        description="Cloud Control identifier of the resource to fetch",
    )


class PaginatedCloudControlResourceRequest(ResourceRequestModel):
    type_name: str = Field(
        ...,
        description="CloudFormation type name to list, e.g. AWS::IAM::Role",
    )
    use_get_resource_api: bool = Field(
        default=False,
        description="When True, hydrate each listed identifier with GetResource",
    )
    resource_scope: CloudControlResourceScope = Field(
        default="auto",
        description="Whether this Cloud Control type is regional, global, or inferred",
    )
