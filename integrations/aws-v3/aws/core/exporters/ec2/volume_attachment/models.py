from typing import Optional
from pydantic.v1 import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class EC2VolumeAttachmentProperties(BaseModel):
    """Properties for an EC2 VolumeAttachment resource."""

    VolumeId: str = Field(default_factory=str)
    InstanceId: str = Field(default_factory=str)
    Device: Optional[str] = None
    State: Optional[str] = None
    AttachTime: Optional[str] = None
    DeleteOnTermination: Optional[bool] = None

    class Config:
        extra = "allow"
        allow_population_by_field_name = True


class EC2VolumeAttachment(ResourceModel[EC2VolumeAttachmentProperties]):
    """EC2 VolumeAttachment resource model."""

    Type: str = "AWS::EC2::VolumeAttachment"
    Properties: EC2VolumeAttachmentProperties = Field(
        default_factory=EC2VolumeAttachmentProperties
    )


class SingleEC2VolumeAttachmentRequest(ResourceRequestModel):
    """Options for exporting a single EC2 VolumeAttachment."""

    volume_id: str = Field(
        ..., description="The ID of the EBS volume to export attachments for"
    )


class PaginatedEC2VolumeAttachmentRequest(ResourceRequestModel):
    """Options for exporting all EC2 VolumeAttachments in a region."""

    pass
