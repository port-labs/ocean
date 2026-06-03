from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field, BaseModel
from typing import List, Literal
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration


class RegionPolicy(BaseModel):
    allow: List[str] = Field(
        default_factory=list,
        title="Allow Regions",
        description="Regions to exclusively allow e.g. ['us-east-1', 'eu-west-1']. If set, only these regions are synced.",
    )
    deny: List[str] = Field(
        default_factory=list,
        title="Deny Regions",
        description="Regions to exclude e.g. ['us-east-1', 'eu-west-1']. If set, all regions except these are synced.",
    )


class AWSResourceSelector(Selector):
    region_policy: RegionPolicy = Field(
        alias="regionPolicy",
        default_factory=RegionPolicy,
        title="Region Policy",
        description="Controls which AWS regions to include or exclude during resync. "
        "Set 'allow' to sync only specific regions, or 'deny' to exclude specific regions. "
        "If both are empty, all regions are synced. "
        'Example: {"allow": ["us-east-1", "eu-west-1"]} or {"deny": ["cn-north-1"]}.',
    )
    include_actions: List[str] = Field(
        alias="includeActions",
        default_factory=list,
        max_items=3,
        title="Include Actions",
        description="Additional AWS resource types to include when fetching resources (max 3). "
        "EC2 Action Example: [DescribeInstanceStatusAction].",
    )
    max_concurrent_accounts: int = Field(
        alias="maxConcurrentAccounts",
        default=5,
        title="Max Concurrent Accounts",
        description="Maximum number of AWS accounts to process concurrently. "
        "Higher values speed up resync but increase API rate limit pressure and memory usage. "
        "Recommended range: 2-10. Reduce if you encounter throttling errors.",
        gte=1,
    )

    def is_region_allowed(self, region: str) -> bool:
        """
        Determines if a given region is allowed based on the query regions policy.
        This method checks the `region_policy` attribute to decide if the specified
        region should be allowed or denied. The policy can contain "allow" and "deny" lists
        which dictate the behavior.

        Scenarios:
        - If `region_policy` is not set or empty, the method returns True, allowing all regions.
        - If the region is listed in the "deny" list of `region_policy`, the method returns False.
        - If the region is listed in the "allow" list of `region_policy`, the method returns True.
        - If the region is not listed in either "allow" or "deny" lists, the method returns False.
        - If the region is listed in both "allow" and "deny" lists, the method returns False.
        - If the policy denies regions but does not explicitly allow any, and the specific region is not in the deny list, then the region is considered allowed.
        - If the policy allows regions but does not explicitly deny any, and the specific region is not in the allow list, then the region is considered denied.
        Args:
            region (str): The region to be checked.

        Returns:
            bool: True if the region is allowed, False otherwise.
        """
        if not self.region_policy.allow and not self.region_policy.deny:
            return True
        if region in self.region_policy.deny:
            return False
        if region in self.region_policy.allow:
            return True
        if self.region_policy.deny and not self.region_policy.allow:
            return True
        if self.region_policy.allow and not self.region_policy.deny:
            return False
        return False


class AWSResourceConfig(ResourceConfig):
    selector: AWSResourceSelector = Field(
        title="Selector",
        description="Selector for the AWS resource.",
    )


class AWSS3BucketResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::S3::Bucket"] = Field(
        title="AWS S3 Bucket",
        description="AWS S3 Bucket resource kind.",
    )


class AWSEC2InstanceResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::EC2::Instance"] = Field(
        title="AWS EC2 Instance",
        description="AWS EC2 Instance resource kind.",
    )


class AWSECSClusterResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::ECS::Cluster"] = Field(
        title="AWS ECS Cluster",
        description="AWS ECS Cluster resource kind.",
    )


class AWSOrganizationsAccountResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::Organizations::Account"] = Field(
        title="AWS Organizations Account",
        description="AWS Organizations Account resource kind.",
    )


class AWSAccountInfoResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::Account::Info"] = Field(
        title="AWS Account Info",
        description="AWS Account Info resource kind.",
    )


class AWSRDSDBInstanceResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::RDS::DBInstance"] = Field(
        title="AWS RDS DB Instance",
        description="AWS RDS DB Instance resource kind.",
    )


class AWSRDSDBClusterResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::RDS::DBCluster"] = Field(
        title="AWS RDS DB Cluster",
        description="AWS RDS DB Cluster resource kind.",
    )


class AWSEKSClusterResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::EKS::Cluster"] = Field(
        title="AWS EKS Cluster",
        description="AWS EKS Cluster resource kind.",
    )


class AWSLambdaFunctionResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::Lambda::Function"] = Field(
        title="AWS Lambda Function",
        description="AWS Lambda Function resource kind.",
    )


class AWSECSServiceResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::ECS::Service"] = Field(
        title="AWS ECS Service",
        description="AWS ECS Service resource kind.",
    )


class AWSSQSQueueResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::SQS::Queue"] = Field(
        title="AWS SQS Queue",
        description="AWS SQS Queue resource kind.",
    )


class AWSECRRepositoryResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::ECR::Repository"] = Field(
        title="AWS ECR Repository",
        description="AWS ECR Repository resource kind.",
    )


class AWSECSTaskDefinitionResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::ECS::TaskDefinition"] = Field(
        title="AWS ECS Task Definition",
        description="AWS ECS Task Definition resource kind.",
    )


class AWSMSKClusterResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::MSK::Cluster"] = Field(
        title="AWS MSK Cluster",
        description="AWS MSK Cluster resource kind.",
    )


class AWSMSKServerlessClusterResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::MSK::ServerlessCluster"] = Field(
        title="AWS MSK Serverless Cluster",
        description="AWS MSK Serverless Cluster resource kind.",
    )


class AWSElastiCacheClusterResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::ElastiCache::Cluster"] = Field(
        title="AWS ElastiCache Cluster",
        description="AWS ElastiCache Cluster resource kind.",
    )


class AWSMemoryDbUserResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::MemoryDB::User"] = Field(
        title="AWS MemoryDB User",
        description="AWS MemoryDB User resource kind.",
    )


class AWSEC2VolumeResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::EC2::Volume"] = Field(
        title="AWS EC2 Volume",
        description="AWS EC2 Volume resource kind.",
    )


class AWSCodePipelinePipelineStageResourceConfig(AWSResourceConfig):
    kind: Literal["AWS::CodePipeline::Stage"] = Field(
        title="AWS Code Pipeline Pipeline Stage",
        description="AWS CodePipeline Pipeline Stage resource kind.",
    )


class AWSPortAppConfig(PortAppConfig):
    resources: List[
        AWSS3BucketResourceConfig
        | AWSEC2InstanceResourceConfig
        | AWSECSClusterResourceConfig
        | AWSOrganizationsAccountResourceConfig
        | AWSAccountInfoResourceConfig
        | AWSRDSDBInstanceResourceConfig
        | AWSRDSDBClusterResourceConfig
        | AWSEKSClusterResourceConfig
        | AWSLambdaFunctionResourceConfig
        | AWSECSServiceResourceConfig
        | AWSECSTaskDefinitionResourceConfig
        | AWSSQSQueueResourceConfig
        | AWSECRRepositoryResourceConfig
        | AWSMSKClusterResourceConfig
        | AWSMSKServerlessClusterResourceConfig
        | AWSElastiCacheClusterResourceConfig
        | AWSMemoryDbUserResourceConfig
        | AWSEC2VolumeResourceConfig
        | AWSCodePipelinePipelineStageResourceConfig
    ] = Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations to sync from AWS.",
    )  # type: ignore[assignment]


class AWSIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AWSPortAppConfig
