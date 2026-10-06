from typing import Any
from datetime import datetime
from pydantic import Field, ConfigDict
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class EbsVolumeProperties(BaseAWSPropertiesModel):
    model_config = ConfigDict(extra="allow")

    VolumeId: str = Field(default_factory=str)
    VolumeType: str | None = None
    Size: int | None = None
    Iops: int | None = None
    Throughput: int | None = None
    AvailabilityZone: str | None = None
    State: str | None = None
    CreateTime: datetime | None = None
    Tags: list[dict[str, Any]] | None = None
    Encrypted: bool | None = None
    SnapshotId: str | None = None
    Attachments: list[dict[str, Any]] | None = None
    MultiAttachEnabled: bool | None = None
    KmsKeyId: str | None = None
    AutoEnableIO: bool | None = None


class EbsVolume(ResourceModel[EbsVolumeProperties]):
    Type: str = "AWS::EC2::Volume"
    Properties: EbsVolumeProperties = Field(default_factory=EbsVolumeProperties)


class SingleEbsVolumeRequest(ResourceRequestModel):
    """Options for exporting a single EBS volume."""

    volume_id: str = Field(..., description="The ID of the EBS volume to export")


class PaginatedEbsVolumeRequest(ResourceRequestModel):
    """Options for exporting all EBS volumes in a region."""

    pass
