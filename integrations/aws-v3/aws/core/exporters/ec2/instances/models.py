from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class EC2InstanceProperties(BaseModel):
    """Properties for an EC2 instance resource."""

    # Core instance identification
    InstanceId: str = Field(default_factory=str)
    ImageId: Optional[str] = None
    InstanceType: Optional[str] = None

    # Instance state (actual field name from describe_instances)
    State: Optional[Dict[str, Any]] = None  # {Code: int, Name: str}

    # Network information (actual field names from describe_instances)
    PrivateIpAddress: Optional[str] = None
    PublicIpAddress: Optional[str] = None  # Public IP address
    PrivateDnsName: Optional[str] = None
    PublicDnsName: Optional[str] = None  # Public DNS name

    # Placement and location
    Placement: Optional[Dict[str, Any]] = (
        None  # Contains AvailabilityZone, GroupName, Tenancy
    )

    # VPC information
    VpcId: Optional[str] = None
    SubnetId: Optional[str] = None

    # Security (actual field name from describe_instances)
    SecurityGroups: Optional[List[Dict[str, Any]]] = None  # Security groups
    KeyName: Optional[str] = None

    # Instance configuration
    LaunchTime: Optional[datetime] = None
    Architecture: Optional[str] = None
    Hypervisor: Optional[str] = None
    VirtualizationType: Optional[str] = None
    Platform: Optional[str] = None
    PlatformDetails: Optional[str] = None

    # Storage (actual field name from describe_instances)
    RootDeviceType: Optional[str] = None
    RootDeviceName: Optional[str] = None
    BlockDeviceMappings: Optional[List[Dict[str, Any]]] = None
    EbsOptimized: Optional[bool] = None

    # Monitoring and management
    Monitoring: Optional[Dict[str, Any]] = None
    IamInstanceProfile: Optional[Dict[str, Any]] = None

    # Network interfaces (actual field name from describe_instances)
    NetworkInterfaces: Optional[List[Dict[str, Any]]] = None
    SourceDestCheck: Optional[bool] = None

    # CPU options
    CpuOptions: Optional[Dict[str, Any]] = None

    # Tags and metadata (actual field name from describe_instances)
    Tags: Optional[List[Dict[str, Any]]] = None
    ClientToken: Optional[str] = None

    # Additional fields that may be present
    AmiLaunchIndex: Optional[int] = None
    ProductCodes: Optional[List[Dict[str, Any]]] = None
    Reason: Optional[str] = None

    # State transition information
    StateTransitionReason: Optional[str] = None
    StateReason: Optional[Dict[str, Any]] = None  # {Code: str, Message: str}

    # Enhanced networking
    EnaSupport: Optional[bool] = None

    # Usage information
    UsageOperation: Optional[str] = None
    UsageOperationUpdateTime: Optional[datetime] = None

    # DNS options
    PrivateDnsNameOptions: Optional[Dict[str, Any]] = None

    # Performance options
    NetworkPerformanceOptions: Optional[Dict[str, Any]] = None

    # Operator information
    Operator: Optional[Dict[str, Any]] = None

    # Custom fields added by actions
    InstanceArn: Optional[str] = None  # Added by GetInstanceArnAction

    # Status fields added by GetInstanceStatusAction
    InstanceStatus: Optional[Dict[str, Any]] = None
    SystemStatus: Optional[Dict[str, Any]] = None
    Events: Optional[List[Dict[str, Any]]] = None

    # Optional fields for newer instance types
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
