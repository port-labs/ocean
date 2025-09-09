from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class EC2InstanceProperties(BaseModel):
    """Properties for an EC2 instance resource."""

    AmiLaunchIndex: Optional[int] = None
    Architecture: Optional[str] = None
    AvailabilityZone: Optional[str] = None
    BlockDeviceMappings: Optional[List[Dict[str, Any]]] = None
    BootMode: Optional[str] = None
    CapacityReservationSpecification: Optional[Dict[str, Any]] = None
    ClientToken: Optional[str] = None
    CpuOptions: Optional[Dict[str, Any]] = None
    CurrentInstanceBootMode: Optional[str] = None
    EbsOptimized: Optional[bool] = None
    EnclaveOptions: Optional[Dict[str, Any]] = None
    EnaSupport: Optional[bool] = None
    Events: Optional[List[Dict[str, Any]]] = None
    HibernationOptions: Optional[Dict[str, Any]] = None
    Hypervisor: Optional[str] = None
    ImageId: Optional[str] = None
    InstanceArn: Optional[str] = None
    InstanceId: str = Field(default_factory=str)
    InstanceStatus: Optional[Dict[str, Any]] = None
    InstanceState: Optional[Dict[str, Any]] = None
    InstanceType: Optional[str] = None
    KeyName: Optional[str] = None
    LaunchTime: Optional[datetime] = None
    MaintenanceOptions: Optional[Dict[str, Any]] = None
    MetadataOptions: Optional[Dict[str, Any]] = None
    Monitoring: Optional[Dict[str, Any]] = None
    NetworkInterfaces: Optional[List[Dict[str, Any]]] = None
    NetworkPerformanceOptions: Optional[Dict[str, Any]] = None
    Operator: Optional[Dict[str, Any]] = None
    Placement: Optional[Dict[str, Any]] = None
    Platform: Optional[str] = None
    PlatformDetails: Optional[str] = None
    PrivateDnsName: Optional[str] = None
    PrivateDnsNameOptions: Optional[Dict[str, Any]] = None
    PrivateIpAddress: Optional[str] = None
    ProductCodes: Optional[List[Dict[str, Any]]] = None
    PublicDnsName: Optional[str] = None
    PublicIpAddress: Optional[str] = None
    Reason: Optional[str] = None
    RootDeviceName: Optional[str] = None
    RootDeviceType: Optional[str] = None
    SecurityGroups: Optional[List[Dict[str, Any]]] = None
    SourceDestCheck: Optional[bool] = None
    State: Optional[Dict[str, Any]] = None
    StateReason: Optional[Dict[str, Any]] = None
    StateTransitionReason: Optional[str] = None
    SubnetId: Optional[str] = None
    SystemStatus: Optional[Dict[str, Any]] = None
    Tags: Optional[List[Dict[str, Any]]] = None
    UsageOperation: Optional[str] = None
    UsageOperationUpdateTime: Optional[datetime] = None
    VirtualizationType: Optional[str] = None
    VpcId: Optional[str] = None

    class Config:
        extra = "allow"
        allow_population_by_name = True


class EC2Instance(ResourceModel[EC2InstanceProperties]):
    """EC2 Instance resource model using the generic ResourceModel pattern."""

    Type: str = "AWS::EC2::Instance"
    Properties: EC2InstanceProperties = Field(default_factory=EC2InstanceProperties)


class SingleEC2InstanceRequest(ResourceRequestModel):
    """Options for exporting a single EC2 instance."""

    instance_id: str = Field(..., description="The ID of the EC2 instance to export")


class PaginatedEC2InstanceRequest(ResourceRequestModel):
    """Options for exporting paginated EC2 instances."""
