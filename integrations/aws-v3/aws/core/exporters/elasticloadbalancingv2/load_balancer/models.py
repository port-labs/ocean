from typing import Optional, Any
from pydantic.v1 import BaseModel, Field
from aws.core.modeling.resource_models import ResourceModel, ResourceRequestModel


class LoadBalancerProperties(BaseModel):
    LoadBalancerArn: str = Field(default_factory=str)
    LoadBalancerName: str = Field(default_factory=str)
    DNSName: Optional[str] = Field(default=None)
    CanonicalHostedZoneId: Optional[str] = Field(default=None)
    CreatedTime: Optional[str] = Field(default=None)
    Scheme: Optional[str] = Field(default=None)
    VpcId: Optional[str] = Field(default=None)
    State: Optional[dict[str, Any]] = Field(default=None)
    Type: Optional[str] = Field(default=None)
    AvailabilityZones: Optional[list[dict[str, Any]]] = Field(default=None)
    SecurityGroups: Optional[list[str]] = Field(default=None)
    IpAddressType: Optional[str] = Field(default=None)
    CustomerOwnedIpv4Pool: Optional[str] = Field(default=None)
    EnforceSecurityGroupInboundRulesOnPrivateLinkTraffic: Optional[str] = Field(
        default=None
    )
    Tags: Optional[list[dict[str, Any]]] = Field(default=None)

    class Config:
        allow_population_by_field_name = True
        extra = "allow"


class LoadBalancer(ResourceModel[LoadBalancerProperties]):
    Type: str = "AWS::ElasticLoadBalancingV2::LoadBalancer"
    Properties: LoadBalancerProperties = Field(
        default_factory=LoadBalancerProperties
    )


class SingleLoadBalancerRequest(ResourceRequestModel):
    """Options for exporting a single ELBv2 load balancer."""

    load_balancer_arn: str = Field(
        ..., description="The ARN of the load balancer to export"
    )


class PaginatedLoadBalancerRequest(ResourceRequestModel):
    """Options for exporting all ELBv2 load balancers in a region."""

    pass
