import enum


ACCOUNT_ID_PROPERTY = "__AccountId"
KIND_PROPERTY = "__Kind"
REGION_PROPERTY = "__Region"


class ResourceKindsWithSpecialHandling(enum.StrEnum):
    """
    Resource kinds with special handling
    These resource kinds are handled separately from the other resource kinds
    """

    ACCOUNT = "AWS::Organizations::Account"
    CLOUDRESOURCE = "cloudResource"
    EC2 = "AWS::EC2::Instance"
    CLOUDFORMATION = "AWS::CloudFormation::Stack"
    LOADBALANCER = "AWS::ElasticLoadBalancingV2::LoadBalancer"
    ACM = "AWS::ACMPCA::Certificate"
