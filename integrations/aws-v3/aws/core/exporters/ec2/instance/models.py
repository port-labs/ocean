from typing import Any
from datetime import datetime

from pydantic import ConfigDict, Field
from aws.core.modeling.resource_models import (
    ResourceModel,
    ResourceRequestModel,
    BaseAWSPropertiesModel,
)


class EC2InstanceProperties(BaseAWSPropertiesModel):
    """Properties for an EC2 instance resource."""

    model_config = ConfigDict(extra="allow")

    AmiLaunchIndex: int | None = None
    Architecture: str | None = None
    AvailabilityZone: str | None = None
    BlockDeviceMappings: list[dict[str, Any]] | None = None
    BootMode: str | None = None
    CapacityReservationSpecification: dict[str, Any] | None = None
    ClientToken: str | None = None
    CpuOptions: dict[str, Any] | None = None
    CurrentInstanceBootMode: str | None = None
    EbsOptimized: bool | None = None
    EnclaveOptions: dict[str, Any] | None = None
    EnaSupport: bool | None = None
    Events: list[dict[str, Any]] | None = None
    HibernationOptions: dict[str, Any] | None = None
    Hypervisor: str | None = None
    ImageId: str | None = None
    InstanceArn: str | None = None
    InstanceId: str = Field(default_factory=str)
    InstanceStatus: dict[str, Any] | None = None
    InstanceState: dict[str, Any] | None = None
    InstanceType: str | None = None
    KeyName: str | None = None
    LaunchTime: datetime | None = None
    MaintenanceOptions: dict[str, Any] | None = None
    MetadataOptions: dict[str, Any] | None = None
    Monitoring: dict[str, Any] | None = None
    NetworkInterfaces: list[dict[str, Any]] | None = None
    NetworkPerformanceOptions: dict[str, Any] | None = None
    Operator: dict[str, Any] | None = None
    Placement: dict[str, Any] | None = None
    Platform: str | None = None
    PlatformDetails: str | None = None
    PrivateDnsName: str | None = None
    PrivateDnsNameOptions: dict[str, Any] | None = None
    PrivateIpAddress: str | None = None
    ProductCodes: list[dict[str, Any]] | None = None
    PublicDnsName: str | None = None
    PublicIpAddress: str | None = None
    Reason: str | None = None
    RootDeviceName: str | None = None
    RootDeviceType: str | None = None
    SecurityGroups: list[dict[str, Any]] | None = None
    SourceDestCheck: bool | None = None
    State: dict[str, Any] | None = None
    StateReason: dict[str, Any] | None = None
    StateTransitionReason: str | None = None
    SubnetId: str | None = None
    SystemStatus: dict[str, Any] | None = None
    Tags: list[dict[str, Any]] | None = None
    UsageOperation: str | None = None
    UsageOperationUpdateTime: datetime | None = None
    VirtualizationType: str | None = None
    VpcId: str | None = None


class EC2Instance(ResourceModel[EC2InstanceProperties]):
    """EC2 Instance resource model using the generic ResourceModel pattern."""

    Type: str = "AWS::EC2::Instance"
    Properties: EC2InstanceProperties = Field(default_factory=EC2InstanceProperties)


class SingleEC2InstanceRequest(ResourceRequestModel):
    """Options for exporting a single EC2 instance."""

    instance_id: str = Field(..., description="The ID of the EC2 instance to export")


class PaginatedEC2InstanceRequest(ResourceRequestModel):
    """Options for exporting paginated EC2 instances."""
