from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aws.core.exporters.aws_lambda.function.exporter import LambdaFunctionExporter
from aws.core.exporters.aws_lambda.function.models import (
    PaginatedLambdaFunctionRequest,
    SingleLambdaFunctionRequest,
)
from aws.core.exporters.codebuild import (
    CodeBuildBuildRunExporter,
    CodeBuildProjectExporter,
    PaginatedBuildRunRequest,
    PaginatedCodeBuildProjectRequest,
)
from aws.core.exporters.codedeploy import (
    CodeDeployApplicationExporter,
    CodeDeployDeploymentExporter,
    CodeDeployDeploymentGroupExporter,
    CodeDeployDeploymentTargetExporter,
    PaginatedCodeDeployApplicationRequest,
    PaginatedCodeDeployDeploymentGroupRequest,
    PaginatedCodeDeployDeploymentRequest,
    PaginatedCodeDeployDeploymentTargetRequest,
)
from aws.core.exporters.codepipeline import (
    CodePipelineActionExecutionExporter,
    CodePipelineActionExporter,
    CodePipelinePipelineExecutionExporter,
    CodePipelineStageExporter,
    PaginatedCodePipelineActionExecutionRequest,
    PaginatedCodePipelineActionRequest,
    PaginatedCodePipelineStageRequest,
    PaginatedPipelineExecutionRequest,
    PaginatedPipelineRequest,
    PipelineExporter,
)
from aws.core.exporters.dynamodb import DynamoDBTableExporter
from aws.core.exporters.dynamodb.table.models import PaginatedTableRequest
from aws.core.exporters.ec2.instance import (
    EC2InstanceExporter,
    PaginatedEC2InstanceRequest,
)
from aws.core.exporters.ec2.volume import EbsVolumeExporter
from aws.core.exporters.ec2.volume.models import PaginatedEbsVolumeRequest
from aws.core.exporters.ecr import EcrRepositoryExporter
from aws.core.exporters.ecr.repository.models import PaginatedRepositoryRequest
from aws.core.exporters.ecs.cluster.exporter import EcsClusterExporter
from aws.core.exporters.ecs.cluster.models import PaginatedClusterRequest
from aws.core.exporters.ecs.service.exporter import EcsServiceExporter
from aws.core.exporters.ecs.service.models import PaginatedServiceRequest
from aws.core.exporters.ecs.task_definition.exporter import EcsTaskDefinitionExporter
from aws.core.exporters.ecs.task_definition.models import PaginatedTaskDefinitionRequest
from aws.core.exporters.eks.cluster.exporter import EksClusterExporter
from aws.core.exporters.eks.cluster.models import PaginatedEksClusterRequest
from aws.core.exporters.elasticache import ElastiCacheClusterExporter
from aws.core.exporters.elasticache.cluster.models import PaginatedCacheClusterRequest
from aws.core.exporters.memorydb.user.exporter import MemoryDbUserExporter
from aws.core.exporters.memorydb.user.models import PaginatedMemoryDbUserRequest
from aws.core.exporters.msk import MskClusterExporter, MskServerlessClusterExporter
from aws.core.exporters.msk.cluster.models import PaginatedMskClusterRequest
from aws.core.exporters.msk.serverless_cluster.models import (
    PaginatedMskServerlessClusterRequest,
)
from aws.core.exporters.rds.db_cluster.exporter import RdsDbClusterExporter
from aws.core.exporters.rds.db_cluster.models import PaginatedDbClusterRequest
from aws.core.exporters.rds.db_instance.exporter import RdsDbInstanceExporter
from aws.core.exporters.rds.db_instance.models import PaginatedDbInstanceRequest
from aws.core.exporters.s3 import PaginatedBucketRequest, S3BucketExporter
from aws.core.exporters.s3.bucket.models import SingleBucketRequest
from aws.core.exporters.ses import (
    PaginatedConfigurationSetRequest,
    PaginatedEmailIdentityRequest,
    SesConfigurationSetExporter,
    SesEmailIdentityExporter,
)
from aws.core.exporters.sqs import SqsQueueExporter
from aws.core.exporters.sqs.queue.models import PaginatedQueueRequest
from aws.core.helpers.types import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.utils import RegionHelper


@dataclass(frozen=True)
class LiveEventContext:
    identifier: str
    account_id: str
    region: str


@dataclass
class ExporterMetadata:
    exporter: type[IResourceExporter[Any]]
    paginated_request_model: type[ResourceRequestModel]
    regional: bool = True
    live_event_request_factory: (
        Callable[[LiveEventContext, list[str]], ResourceRequestModel] | None
    ) = None
    live_event_delete_properties_factory: (
        Callable[[LiveEventContext], dict[str, str]] | None
    ) = None

    @property
    def supports_live_events(self) -> bool:
        return (
            self.live_event_request_factory is not None
            and self.live_event_delete_properties_factory is not None
        )


def _s3_bucket_arn(bucket_name: str) -> str:
    partition = RegionHelper.get_partition()
    return f"arn:{partition}:s3:::{bucket_name}"


def _s3_bucket_live_event_request(
    context: LiveEventContext, include_actions: list[str]
) -> SingleBucketRequest:
    return SingleBucketRequest(
        bucket_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _s3_bucket_live_event_delete_properties(context: LiveEventContext) -> dict[str, str]:
    return {
        "Arn": _s3_bucket_arn(context.identifier),
        "BucketName": context.identifier,
    }


def _lambda_function_arn(context: LiveEventContext) -> str:
    partition = RegionHelper.get_partition()
    return (
        f"arn:{partition}:lambda:{context.region}:{context.account_id}:"
        f"function:{context.identifier}"
    )


def _lambda_function_live_event_request(
    context: LiveEventContext, include_actions: list[str]
) -> SingleLambdaFunctionRequest:
    return SingleLambdaFunctionRequest(
        function_name=context.identifier,
        region=context.region,
        account_id=context.account_id,
        include=include_actions,
    )


def _lambda_function_live_event_delete_properties(
    context: LiveEventContext,
) -> dict[str, str]:
    return {
        "FunctionArn": _lambda_function_arn(context),
        "FunctionName": context.identifier,
    }


kind_to_export_metadata: dict[ObjectKind, ExporterMetadata] = {
    ObjectKind.S3_BUCKET: ExporterMetadata(
        S3BucketExporter,
        PaginatedBucketRequest,
        regional=False,
        live_event_request_factory=_s3_bucket_live_event_request,
        live_event_delete_properties_factory=_s3_bucket_live_event_delete_properties,
    ),
    ObjectKind.EC2_INSTANCE: ExporterMetadata(
        EC2InstanceExporter, PaginatedEC2InstanceRequest
    ),
    ObjectKind.ECS_CLUSTER: ExporterMetadata(
        EcsClusterExporter, PaginatedClusterRequest
    ),
    ObjectKind.EKS_CLUSTER: ExporterMetadata(
        EksClusterExporter, PaginatedEksClusterRequest
    ),
    ObjectKind.RDS_DB_INSTANCE: ExporterMetadata(
        RdsDbInstanceExporter, PaginatedDbInstanceRequest
    ),
    ObjectKind.RDS_DB_CLUSTER: ExporterMetadata(
        RdsDbClusterExporter, PaginatedDbClusterRequest
    ),
    ObjectKind.LAMBDA_FUNCTION: ExporterMetadata(
        LambdaFunctionExporter,
        PaginatedLambdaFunctionRequest,
        live_event_request_factory=_lambda_function_live_event_request,
        live_event_delete_properties_factory=_lambda_function_live_event_delete_properties,
    ),
    ObjectKind.ECS_SERVICE: ExporterMetadata(
        EcsServiceExporter, PaginatedServiceRequest
    ),
    ObjectKind.ECS_TASK_DEFINITION: ExporterMetadata(
        EcsTaskDefinitionExporter, PaginatedTaskDefinitionRequest
    ),
    ObjectKind.SQS_QUEUE: ExporterMetadata(SqsQueueExporter, PaginatedQueueRequest),
    ObjectKind.ECR_REPOSITORY: ExporterMetadata(
        EcrRepositoryExporter, PaginatedRepositoryRequest
    ),
    ObjectKind.MSK_SERVERLESS_CLUSTER: ExporterMetadata(
        MskServerlessClusterExporter, PaginatedMskServerlessClusterRequest
    ),
    ObjectKind.MEMORYDB_USER: ExporterMetadata(
        MemoryDbUserExporter, PaginatedMemoryDbUserRequest
    ),
    ObjectKind.MSK_CLUSTER: ExporterMetadata(
        MskClusterExporter, PaginatedMskClusterRequest
    ),
    ObjectKind.ELASTICACHE_CLUSTER: ExporterMetadata(
        ElastiCacheClusterExporter, PaginatedCacheClusterRequest
    ),
    ObjectKind.EC2_VOLUME: ExporterMetadata(
        EbsVolumeExporter, PaginatedEbsVolumeRequest
    ),
    ObjectKind.CODEBUILD_PROJECT: ExporterMetadata(
        CodeBuildProjectExporter, PaginatedCodeBuildProjectRequest
    ),
    ObjectKind.CODEBUILD_BUILD_RUN: ExporterMetadata(
        CodeBuildBuildRunExporter, PaginatedBuildRunRequest
    ),
    ObjectKind.CODEDEPLOY_APPLICATION: ExporterMetadata(
        CodeDeployApplicationExporter, PaginatedCodeDeployApplicationRequest
    ),
    ObjectKind.CODEDEPLOY_DEPLOYMENT_GROUP: ExporterMetadata(
        CodeDeployDeploymentGroupExporter, PaginatedCodeDeployDeploymentGroupRequest
    ),
    ObjectKind.CODEDEPLOY_DEPLOYMENT: ExporterMetadata(
        CodeDeployDeploymentExporter, PaginatedCodeDeployDeploymentRequest
    ),
    ObjectKind.CODEDEPLOY_DEPLOYMENT_TARGET: ExporterMetadata(
        CodeDeployDeploymentTargetExporter, PaginatedCodeDeployDeploymentTargetRequest
    ),
    ObjectKind.CODEPIPELINE_PIPELINE: ExporterMetadata(
        PipelineExporter, PaginatedPipelineRequest
    ),
    ObjectKind.CODEPIPELINE_STAGE: ExporterMetadata(
        CodePipelineStageExporter, PaginatedCodePipelineStageRequest
    ),
    ObjectKind.CODEPIPELINE_ACTION: ExporterMetadata(
        CodePipelineActionExporter, PaginatedCodePipelineActionRequest
    ),
    ObjectKind.CODEPIPELINE_PIPELINE_EXECUTION: ExporterMetadata(
        CodePipelinePipelineExecutionExporter, PaginatedPipelineExecutionRequest
    ),
    ObjectKind.CODEPIPELINE_ACTION_EXECUTION: ExporterMetadata(
        CodePipelineActionExecutionExporter, PaginatedCodePipelineActionExecutionRequest
    ),
    ObjectKind.SES_EMAIL_IDENTITY: ExporterMetadata(
        SesEmailIdentityExporter, PaginatedEmailIdentityRequest
    ),
    ObjectKind.DYNAMODB_TABLE: ExporterMetadata(
        DynamoDBTableExporter, PaginatedTableRequest
    ),
    ObjectKind.SES_CONFIGURATION_SET: ExporterMetadata(
        SesConfigurationSetExporter, PaginatedConfigurationSetRequest
    ),
}
