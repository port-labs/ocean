from pydantic import BaseModel, Field
from typing import List, Optional


class ResourceModel[PropertiesT: BaseModel](BaseModel):
    """
    Generic response model for AWS resources.

    Attributes:
        Type (str): The AWS resource type identifier (e.g., "AWS::S3::Bucket").
        Properties (PropertiesT): The properties of the AWS resource, typed as a Pydantic model.
        account_id (str): The AWS account ID for this resource (aliased as __AccountId).
        region (str): The AWS region for this resource (aliased as __Region).
    """

    Type: str
    Properties: PropertiesT
    account_id: Optional[str] = Field(None, alias="__AccountId")
    region: Optional[str] = Field(None, alias="__Region")

    class Config:
        extra = "ignore"
        """Extra fields not defined in the model will be ignored."""


class ResourceRequestModel(BaseModel):
    """
    Base request parameters for exporting AWS resources.

    Attributes:
        region (str): The AWS region from which to export resources.
        include (List[str]): List of resource types or names to include in the export.
    """

    region: str = Field(..., description="The AWS region to export resources from")
    include: List[str] = Field(
        default_factory=list, description="The resources to include in the export"
    )

    class Config:
        extra = "allow"
        """Extra fields not defined in the model are allowed."""
