from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class EbsVolumeProperties(BaseModel):
    VolumeId: str = Field(default_factory=str)
    VolumeType: Optional[str] = None
    Size: Optional[int] = None
    Iops: Optional[int] = None
    Throughput: Optional[int] = None
    AvailabilityZone: Optional[str] = None
    State: Optional[str] = None
    CreateTime: Optional[datetime] = None
    Tags: Optional[List[Dict[str, Any]]] = None
    Encrypted: Optional[bool] = None
    SnapshotId: Optional[str] = None
    Attachments: Optional[List[Dict[str, Any]]] = None
    MultiAttachEnabled: Optional[bool] = None
    KmsKeyId: Optional[str] = None
    AutoEnableIO: Optional[bool] = None

    class Config:
        extra = "allow"
        allow_population_by_field_name = True


class EbsVolume(ResourceModel[EbsVolumeProperties]):
    Type: str = "AWS::EC2::Volume"
    Properties: EbsVolumeProperties = Field(default_factory=EbsVolumeProperties)


class SingleEbsVolumeRequest(ResourceRequestModel):
    """Options for exporting a single EBS volume."""

    volume_id: str = Field(..., description="The ID of the EBS volume to export")


class PaginatedEbsVolumeRequest(ResourceRequestModel):
    """Options for exporting all EBS volumes in a region."""

    pass
