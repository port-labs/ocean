from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic.v1 import Field, BaseModel, ValidationError
from pydantic.v1.error_wrappers import ErrorWrapper
from typing import ClassVar, List, Literal
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from feature_flags import is_aws_v3_custom_kinds_enabled

AWS_CLOUD_CONTROL_TYPE_PATTERN = r"^AWS::[A-Za-z0-9]+::[A-Za-z0-9]+$"


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
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "s3:ListAllMyBuckets",
        "s3:GetBucketTagging",
    )
    kind: Literal["AWS::S3::Bucket"] = Field(
        title="AWS S3 Bucket",
        description="AWS S3 Bucket resource kind.",
    )


class AWSEC2InstanceResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("ec2:DescribeInstances",)
    kind: Literal["AWS::EC2::Instance"] = Field(
        title="AWS EC2 Instance",
        description="AWS EC2 Instance resource kind.",
    )


class AWSECSClusterResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "ecs:ListClusters",
        "ecs:DescribeClusters",
    )
    kind: Literal["AWS::ECS::Cluster"] = Field(
        title="AWS ECS Cluster",
        description="AWS ECS Cluster resource kind.",
    )


class AWSOrganizationsAccountResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("organizations:ListAccounts",)
    kind: Literal["AWS::Organizations::Account"] = Field(
        title="AWS Organizations Account",
        description="AWS Organizations Account resource kind.",
    )


class AWSAccountInfoResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("sts:GetCallerIdentity",)
    kind: Literal["AWS::Account::Info"] = Field(
        title="AWS Account Info",
        description="AWS Account Info resource kind.",
    )


class AWSRDSDBInstanceResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("rds:DescribeDBInstances",)
    kind: Literal["AWS::RDS::DBInstance"] = Field(
        title="AWS RDS DB Instance",
        description="AWS RDS DB Instance resource kind.",
    )


class AWSRDSDBClusterResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("rds:DescribeDBClusters",)
    kind: Literal["AWS::RDS::DBCluster"] = Field(
        title="AWS RDS DB Cluster",
        description="AWS RDS DB Cluster resource kind.",
    )


class AWSEKSClusterResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "eks:ListClusters",
        "eks:DescribeCluster",
    )
    kind: Literal["AWS::EKS::Cluster"] = Field(
        title="AWS EKS Cluster",
        description="AWS EKS Cluster resource kind.",
    )


class AWSLambdaFunctionResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("lambda:ListFunctions",)
    kind: Literal["AWS::Lambda::Function"] = Field(
        title="AWS Lambda Function",
        description="AWS Lambda Function resource kind.",
    )


class AWSECSServiceResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "ecs:ListClusters",
        "ecs:ListServices",
        "ecs:DescribeServices",
    )
    kind: Literal["AWS::ECS::Service"] = Field(
        title="AWS ECS Service",
        description="AWS ECS Service resource kind.",
    )


class AWSSQSQueueResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "sqs:ListQueues",
        "sqs:GetQueueAttributes",
    )
    kind: Literal["AWS::SQS::Queue"] = Field(
        title="AWS SQS Queue",
        description="AWS SQS Queue resource kind.",
    )


class AWSECRRepositoryResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("ecr:DescribeRepositories",)
    kind: Literal["AWS::ECR::Repository"] = Field(
        title="AWS ECR Repository",
        description="AWS ECR Repository resource kind.",
    )


class AWSECSTaskDefinitionResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "ecs:ListTaskDefinitions",
        "ecs:DescribeTaskDefinition",
    )
    kind: Literal["AWS::ECS::TaskDefinition"] = Field(
        title="AWS ECS Task Definition",
        description="AWS ECS Task Definition resource kind.",
    )


class AWSMSKClusterResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("kafka:ListClusters",)
    kind: Literal["AWS::MSK::Cluster"] = Field(
        title="AWS MSK Cluster",
        description="AWS MSK Cluster resource kind.",
    )


class AWSMSKServerlessClusterResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("kafka:ListClustersV2",)
    kind: Literal["AWS::MSK::ServerlessCluster"] = Field(
        title="AWS MSK Serverless Cluster",
        description="AWS MSK Serverless Cluster resource kind.",
    )


class AWSElastiCacheClusterResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "elasticache:DescribeCacheClusters",
    )
    kind: Literal["AWS::ElastiCache::Cluster"] = Field(
        title="AWS ElastiCache Cluster",
        description="AWS ElastiCache Cluster resource kind.",
    )


class AWSMemoryDbUserResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("memorydb:DescribeUsers",)
    kind: Literal["AWS::MemoryDB::User"] = Field(
        title="AWS MemoryDB User",
        description="AWS MemoryDB User resource kind.",
    )


class AWSEC2VolumeResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = ("ec2:DescribeVolumes",)
    kind: Literal["AWS::EC2::Volume"] = Field(
        title="AWS EC2 Volume",
        description="AWS EC2 Volume resource kind.",
    )


class AWSCodeBuildProjectResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codebuild:ListProjects",
        "codebuild:BatchGetProjects",
    )
    kind: Literal["AWS::CodeBuild::Project"] = Field(
        title="AWS CodeBuild Project",
        description="AWS CodeBuild Project resource kind.",
    )


class AWSCodeBuildBuildRunResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codebuild:ListBuilds",
        "codebuild:BatchGetBuilds",
    )
    kind: Literal["AWS::CodeBuild::BuildRun"] = Field(
        title="AWS CodeBuild BuildRun",
        description="AWS CodeBuild BuildRun resource kind.",
    )


class AWSCodeDeployApplicationResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codedeploy:ListApplications",
        "codedeploy:BatchGetApplications",
        "codedeploy:ListTagsForResource",
    )
    kind: Literal["AWS::CodeDeploy::Application"] = Field(
        title="AWS CodeDeploy Application",
        description="AWS CodeDeploy Application resource kind.",
    )


class AWSCodeDeployDeploymentGroupResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codedeploy:ListApplications",
        "codedeploy:ListDeploymentGroups",
        "codedeploy:BatchGetDeploymentGroups",
    )
    kind: Literal["AWS::CodeDeploy::DeploymentGroup"] = Field(
        title="AWS CodeDeploy Deployment Group",
        description="AWS CodeDeploy Deployment Group resource kind.",
    )


class AWSCodeDeployDeploymentResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codedeploy:ListDeployments",
        "codedeploy:GetDeployment",
    )
    kind: Literal["AWS::CodeDeploy::Deployment"] = Field(
        title="AWS CodeDeploy Deployment",
        description="AWS CodeDeploy Deployment resource kind.",
    )


class AWSCodeDeployDeploymentTargetResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codedeploy:ListDeployments",
        "codedeploy:ListDeploymentTargets",
        "codedeploy:BatchGetDeploymentTargets",
    )
    kind: Literal["AWS::CodeDeploy::DeploymentTarget"] = Field(
        title="AWS CodeDeploy DeploymentTarget",
        description="AWS CodeDeploy Deployment Target resource kind.",
    )


class AWSCodePipelinePipelineResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codepipeline:ListPipelines",
        "codepipeline:GetPipeline",
        "codepipeline:ListTagsForResource",
    )
    kind: Literal["AWS::CodePipeline::Pipeline"] = Field(
        title="AWS CodePipeline Pipeline",
        description="AWS CodePipeline Pipeline resource kind.",
    )


class AWSCodePipelineStageResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codepipeline:ListPipelines",
        "codepipeline:GetPipeline",
    )
    kind: Literal["AWS::CodePipeline::Stage"] = Field(
        title="AWS CodePipeline Stage",
        description="AWS CodePipeline Stage resource kind.",
    )


class AWSCodePipelineActionResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codepipeline:ListPipelines",
        "codepipeline:GetPipeline",
    )
    kind: Literal["AWS::CodePipeline::Action"] = Field(
        title="AWS CodePipeline Action",
        description="AWS CodePipeline Action resource kind.",
    )


class AWSCodePipelinePipelineExecutionResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codepipeline:ListPipelines",
        "codepipeline:ListPipelineExecutions",
        "codepipeline:GetPipelineExecution",
    )
    kind: Literal["AWS::CodePipeline::PipelineExecution"] = Field(
        title="AWS CodePipeline Pipeline Execution",
        description="AWS CodePipeline Pipeline Execution resource kind.",
    )


class AWSCodePipelineActionExecutionResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "codepipeline:ListPipelines",
        "codepipeline:ListActionExecutions",
    )
    kind: Literal["AWS::CodePipeline::ActionExecution"] = Field(
        title="AWS CodePipeline Action Execution",
        description="AWS CodePipeline Action Execution resource kind.",
    )


class AWSSESEmailIdentityResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "ses:ListEmailIdentities",
        "ses:GetEmailIdentity",
    )
    kind: Literal["AWS::SES::EmailIdentity"] = Field(
        title="AWS SES Email Identity",
        description="AWS SES Email Identity resource kind.",
    )


class AWSDynamoDBTableResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "dynamodb:ListTables",
        "dynamodb:DescribeTable",
    )
    kind: Literal["AWS::DynamoDB::Table"] = Field(
        title="AWS DynamoDB Table",
        description="AWS DynamoDB Table resource kind.",
    )


class AWSSESConfigurationSetResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "ses:ListConfigurationSets",
        "ses:GetConfigurationSet",
    )
    kind: Literal["AWS::SES::ConfigurationSet"] = Field(
        title="AWS SES Configuration Set",
        description="AWS SES Configuration Set resource kind.",
    )


class AWSSNSTopicResourceConfig(AWSResourceConfig):
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "sns:ListTopics",
        "sns:GetTopicAttributes",
    )
    kind: Literal["AWS::SNS::Topic"] = Field(
        title="AWS SNS Topic",
        description="AWS SNS Topic resource kind.",
    )


class AWSCustomKindSelector(Selector):
    region_policy: RegionPolicy = Field(
        alias="regionPolicy",
        default_factory=RegionPolicy,
        title="Region Policy",
        description="Controls which AWS regions to include or exclude during resync. "
        "Set 'allow' to sync only specific regions, or 'deny' to exclude specific regions. "
        "If both are empty, all regions are synced. "
        'Example: {"allow": ["us-east-1", "eu-west-1"]} or {"deny": ["cn-north-1"]}.',
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
    use_get_resource_api: bool = Field(
        alias="useGetResourceAPI",
        default=False,
        title="Use Get Resource API",
        description="When enabled, uses the AWS Cloud Control GetResource API to fetch full "
        "resource details instead of relying solely on list results. This makes an additional "
        "API call per resource, which may increase latency and consume more API rate limit quota.",
    )
    resource_scope: Literal["auto", "regional", "global"] = Field(
        alias="resourceScope",
        default="auto",
        title="Resource Scope",
        description="Whether this Cloud Control type is regional, global, or should be inferred "
        "automatically during sync.",
    )

    def is_region_allowed(self, region: str) -> bool:
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


class AWSCustomKindResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Custom AWS Resource Kind",
        description="Map any resource type supported by the "
        "<a target='_blank' href='https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html'>"
        "AWS Cloud Control API</a> by setting kind to the CloudFormation type name "
        "(for example AWS::IAM::Role).",
        regex=AWS_CLOUD_CONTROL_TYPE_PATTERN,
    )
    selector: AWSCustomKindSelector = Field(
        title="Selector",
        description="Selector for the custom AWS Cloud Control resource kind.",
    )


class AWSPortAppConfig(PortAppConfig):
    allow_custom_kinds: ClassVar[bool] = True

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
        | AWSCodeBuildProjectResourceConfig
        | AWSCodeBuildBuildRunResourceConfig
        | AWSCodeDeployApplicationResourceConfig
        | AWSCodeDeployDeploymentGroupResourceConfig
        | AWSCodeDeployDeploymentResourceConfig
        | AWSCodeDeployDeploymentTargetResourceConfig
        | AWSCodePipelinePipelineResourceConfig
        | AWSCodePipelineStageResourceConfig
        | AWSCodePipelineActionResourceConfig
        | AWSCodePipelinePipelineExecutionResourceConfig
        | AWSCodePipelineActionExecutionResourceConfig
        | AWSSESEmailIdentityResourceConfig
        | AWSDynamoDBTableResourceConfig
        | AWSSESConfigurationSetResourceConfig
        | AWSSNSTopicResourceConfig
        | AWSCustomKindResourceConfig
    ] = Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations to sync from AWS.",
    )  # type: ignore[assignment]


async def _ensure_custom_kinds_feature_enabled(config: AWSPortAppConfig) -> None:
    if not any(isinstance(resource, AWSCustomKindResourceConfig) for resource in config.resources):
        return
    if await is_aws_v3_custom_kinds_enabled():
        return
    raise ValidationError(
        [
            ErrorWrapper(
                ValueError(
                    "Custom AWS resource kinds require the "
                    "AWS_V3_CUSTOM_KINDS_ENABLED organization feature flag"
                ),
                loc=("resources",),
            )
        ],
        AWSPortAppConfig,
    )


class AWSAPIPortAppConfig(APIPortAppConfig):
    CONFIG_CLASS = AWSPortAppConfig

    async def get_port_app_config(self, use_cache: bool = True) -> AWSPortAppConfig:
        config = await super().get_port_app_config(use_cache=use_cache)
        await _ensure_custom_kinds_feature_enabled(config)
        return config


class AWSIntegration(BaseIntegration):
    class AppConfigHandlerClass(AWSAPIPortAppConfig):
        pass
