import enum

class ResourceKindsWithSpecialHandling(enum.StrEnum):
    """
    Resource kinds with special handling
    These resource kinds are handled separately from the other resource kinds
    """

    EC2 = "ec2"
    CLOUDFORMATION = "cloudformation"
    LOADBALANCER = "loadbalancer"
    ELASTICACHE = "elasticache"
    ACM = "acm"
