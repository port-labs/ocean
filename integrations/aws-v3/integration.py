from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from aws_integration.overrides import AWSPortAppConfig

# Re-export config models so existing `from integration import ...` keeps working.
from aws_integration.overrides import (  # noqa: F401
    AWS_CLOUD_CONTROL_TYPE_PATTERN,
    AWSAccountInfoResourceConfig,
    AWSCodeBuildBuildRunResourceConfig,
    AWSCodeBuildProjectResourceConfig,
    AWSCodeDeployApplicationResourceConfig,
    AWSCodeDeployDeploymentGroupResourceConfig,
    AWSCodeDeployDeploymentResourceConfig,
    AWSCodeDeployDeploymentTargetResourceConfig,
    AWSCodePipelineActionExecutionResourceConfig,
    AWSCodePipelineActionResourceConfig,
    AWSCodePipelinePipelineExecutionResourceConfig,
    AWSCodePipelinePipelineResourceConfig,
    AWSCodePipelineStageResourceConfig,
    AWSCustomKindResourceConfig,
    AWSCustomKindSelector,
    AWSDynamoDBTableResourceConfig,
    AWSEC2InstanceResourceConfig,
    AWSEC2VolumeResourceConfig,
    AWSECRRepositoryResourceConfig,
    AWSECSClusterResourceConfig,
    AWSECSServiceResourceConfig,
    AWSECSTaskDefinitionResourceConfig,
    AWSEKSClusterResourceConfig,
    AWSElastiCacheClusterResourceConfig,
    AWSLambdaFunctionResourceConfig,
    AWSMemoryDbUserResourceConfig,
    AWSMSKClusterResourceConfig,
    AWSMSKServerlessClusterResourceConfig,
    AWSOrganizationsAccountResourceConfig,
    AWSRDSDBClusterResourceConfig,
    AWSRDSDBInstanceResourceConfig,
    AWSResourceConfig,
    AWSResourceSelector,
    AWSSESConfigurationSetResourceConfig,
    AWSSESEmailIdentityResourceConfig,
    AWSS3BucketResourceConfig,
    AWSSNSTopicResourceConfig,
    AWSSQSQueueResourceConfig,
    RegionPolicy,
)


class AWSIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AWSPortAppConfig
