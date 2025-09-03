from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class EC2InstanceProperties(BaseModel):
    """Properties for an EC2 instance resource."""

    InstanceId: str = Field(default_factory=str)
    ImageId: Optional[str] = None
    InstanceType: Optional[str] = None

    State: Optional[Dict[str, Any]] = None

    PrivateIpAddress: Optional[str] = None
    PublicIpAddress: Optional[str] = None
    PrivateDnsName: Optional[str] = None
    PublicDnsName: Optional[str] = None

    Placement: Optional[Dict[str, Any]] = None

    VpcId: Optional[str] = None
    SubnetId: Optional[str] = None

    SecurityGroups: Optional[List[Dict[str, Any]]] = None
    KeyName: Optional[str] = None

    LaunchTime: Optional[datetime] = None
    Architecture: Optional[str] = None
    Hypervisor: Optional[str] = None
    VirtualizationType: Optional[str] = None
    Platform: Optional[str] = None
    PlatformDetails: Optional[str] = None

    RootDeviceType: Optional[str] = None
    RootDeviceName: Optional[str] = None
    BlockDeviceMappings: Optional[List[Dict[str, Any]]] = None
    EbsOptimized: Optional[bool] = None

    Monitoring: Optional[Dict[str, Any]] = None
    IamInstanceProfile: Optional[Dict[str, Any]] = None

    NetworkInterfaces: Optional[List[Dict[str, Any]]] = None
    SourceDestCheck: Optional[bool] = None

    CpuOptions: Optional[Dict[str, Any]] = None

    Tags: Optional[List[Dict[str, Any]]] = None
    ClientToken: Optional[str] = None

    AmiLaunchIndex: Optional[int] = None
    ProductCodes: Optional[List[Dict[str, Any]]] = None
    Reason: Optional[str] = None

    StateTransitionReason: Optional[str] = None
    StateReason: Optional[Dict[str, Any]] = None

    EnaSupport: Optional[bool] = None

    UsageOperation: Optional[str] = None
    UsageOperationUpdateTime: Optional[datetime] = None

    PrivateDnsNameOptions: Optional[Dict[str, Any]] = None

    NetworkPerformanceOptions: Optional[Dict[str, Any]] = None

    Operator: Optional[Dict[str, Any]] = None

    InstanceArn: Optional[str] = None

    InstanceStatus: Optional[Dict[str, Any]] = None
    SystemStatus: Optional[Dict[str, Any]] = None
    Events: Optional[List[Dict[str, Any]]] = None

    CapacityReservationSpecification: Optional[Dict[str, Any]] = None
    HibernationOptions: Optional[Dict[str, Any]] = None
    MetadataOptions: Optional[Dict[str, Any]] = None
    EnclaveOptions: Optional[Dict[str, Any]] = None
    BootMode: Optional[str] = None
    MaintenanceOptions: Optional[Dict[str, Any]] = None
    CurrentInstanceBootMode: Optional[str] = None

    class Config:
        extra = "forbid"


class EC2Instance(ResourceModel[EC2InstanceProperties]):
    """EC2 Instance resource model using the generic ResourceModel pattern."""

    Type: str = "AWS::EC2::Instance"
    Properties: EC2InstanceProperties = Field(default_factory=EC2InstanceProperties)


class SingleEC2InstanceRequest(ResourceRequestModel):
    """Options for exporting a single EC2 instance."""

    instance_id: str = Field(..., description="The ID of the EC2 instance to export")


class PaginatedEC2InstanceRequest(ResourceRequestModel):
    """Options for exporting paginated EC2 instances."""
