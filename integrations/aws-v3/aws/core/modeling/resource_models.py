from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_pascal
from typing import List


class BaseAWSPropertiesModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ExtraContextModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    AccountId: str | None = None
    Region: str | None = None


class ResourceModel[PropertiesT: BaseModel](BaseModel):
    """
    Generic response model for AWS resources.

    Attributes:
        Type (str): The AWS resource type identifier (e.g., "AWS::S3::Bucket").
        Properties (PropertiesT): The properties of the AWS resource, typed as a Pydantic model.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    Type: str
    Properties: PropertiesT
    ExtraContext: ExtraContextModel = Field(
        default_factory=ExtraContextModel, alias="__ExtraContext"
    )


class ResourceRequestModel(BaseModel):
    """
    Base request parameters for exporting AWS resources.

    Attributes:
        region (str): The AWS region from which to export resources.
        include (List[str]): List of resource types or names to include in the export.
    """

    model_config = ConfigDict(extra="allow")

    region: str = Field(..., description="The AWS region to export resources from")
    account_id: str = Field(
        ..., description="The AWS account ID to export resources from"
    )
    include: List[str] = Field(
        default_factory=list, description="The resources to include in the export"
    )
