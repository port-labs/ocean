from aws.core.exporters.aws_lambda.function.exporter import LambdaFunctionExporter
from aws.core.exporters.aws_lambda.function.live_events import (
    LAMBDA_FUNCTION_LIVE_EVENTS,
)
from aws.core.exporters.aws_lambda.function.models import PaginatedLambdaFunctionRequest
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
from aws.core.exporters.dynamodb.table.live_events import DYNAMODB_TABLE_LIVE_EVENTS
from aws.core.exporters.dynamodb.table.models import PaginatedTableRequest
from aws.core.exporters.ec2.instance import (
    EC2InstanceExporter,
    PaginatedEC2InstanceRequest,
)
from aws.core.exporters.ec2.instance.live_events import EC2_INSTANCE_LIVE_EVENTS
from aws.core.exporters.ec2.volume import EbsVolumeExporter
from aws.core.exporters.ec2.volume.live_events import EC2_VOLUME_LIVE_EVENTS
from aws.core.exporters.ec2.volume.models import PaginatedEbsVolumeRequest
from aws.core.exporters.ecr import EcrRepositoryExporter
from aws.core.exporters.ecr.repository.live_events import ECR_REPOSITORY_LIVE_EVENTS
from aws.core.exporters.ecr.repository.models import PaginatedRepositoryRequest
from aws.core.exporters.ecs.cluster.exporter import EcsClusterExporter
from aws.core.exporters.ecs.cluster.live_events import ECS_CLUSTER_LIVE_EVENTS
from aws.core.exporters.ecs.cluster.models import PaginatedClusterRequest
from aws.core.exporters.ecs.service.exporter import EcsServiceExporter
from aws.core.exporters.ecs.service.models import PaginatedServiceRequest
from aws.core.exporters.ecs.task_definition.exporter import EcsTaskDefinitionExporter
from aws.core.exporters.ecs.task_definition.models import PaginatedTaskDefinitionRequest
from aws.core.exporters.eks.cluster.exporter import EksClusterExporter
from aws.core.exporters.eks.cluster.live_events import EKS_CLUSTER_LIVE_EVENTS
from aws.core.exporters.eks.cluster.models import PaginatedEksClusterRequest
from aws.core.exporters.elasticache import ElastiCacheClusterExporter
from aws.core.exporters.elasticache.cluster.live_events import (
    ELASTICACHE_CLUSTER_LIVE_EVENTS,
)
from aws.core.exporters.elasticache.cluster.models import PaginatedCacheClusterRequest
from aws.core.exporters.memorydb.user.exporter import MemoryDbUserExporter
from aws.core.exporters.memorydb.user.models import PaginatedMemoryDbUserRequest
from aws.core.helpers.metadata.types import ExporterMetadata
from aws.core.exporters.msk import MskClusterExporter, MskServerlessClusterExporter
from aws.core.exporters.msk.cluster.models import PaginatedMskClusterRequest
from aws.core.exporters.msk.serverless_cluster.models import (
    PaginatedMskServerlessClusterRequest,
)
from aws.core.exporters.rds.db_cluster.exporter import RdsDbClusterExporter
from aws.core.exporters.rds.db_cluster.live_events import RDS_DB_CLUSTER_LIVE_EVENTS
from aws.core.exporters.rds.db_cluster.models import PaginatedDbClusterRequest
from aws.core.exporters.rds.db_instance.exporter import RdsDbInstanceExporter
from aws.core.exporters.rds.db_instance.live_events import RDS_DB_INSTANCE_LIVE_EVENTS
from aws.core.exporters.rds.db_instance.models import PaginatedDbInstanceRequest
from aws.core.exporters.s3 import PaginatedBucketRequest, S3BucketExporter
from aws.core.exporters.s3.bucket.live_events import S3_BUCKET_LIVE_EVENTS
from aws.core.exporters.ses import (
    PaginatedConfigurationSetRequest,
    PaginatedEmailIdentityRequest,
    SesConfigurationSetExporter,
    SesEmailIdentityExporter,
)
from aws.core.exporters.ses.configuration_set.live_events import (
    SES_CONFIGURATION_SET_LIVE_EVENTS,
)
from aws.core.exporters.ses.email_identity.live_events import (
    SES_EMAIL_IDENTITY_LIVE_EVENTS,
)
from aws.core.exporters.sns import SNSTopicExporter, PaginatedTopicRequest
from aws.core.exporters.sns.topic.live_events import SNS_TOPIC_LIVE_EVENTS
from aws.core.exporters.sqs import SqsQueueExporter
from aws.core.exporters.sqs.queue.live_events import SQS_QUEUE_LIVE_EVENTS
from aws.core.exporters.sqs.queue.models import PaginatedQueueRequest
from aws.core.helpers.types import ObjectKind

kind_to_export_metadata: dict[ObjectKind, ExporterMetadata] = {
    ObjectKind.S3_BUCKET: ExporterMetadata(
        S3BucketExporter,
        PaginatedBucketRequest,
        regional=False,
        live_events=S3_BUCKET_LIVE_EVENTS,
    ),
    ObjectKind.EC2_INSTANCE: ExporterMetadata(
        EC2InstanceExporter,
        PaginatedEC2InstanceRequest,
        live_events=EC2_INSTANCE_LIVE_EVENTS,
    ),
    ObjectKind.ECS_CLUSTER: ExporterMetadata(
        EcsClusterExporter,
        PaginatedClusterRequest,
        live_events=ECS_CLUSTER_LIVE_EVENTS,
    ),
    ObjectKind.EKS_CLUSTER: ExporterMetadata(
        EksClusterExporter,
        PaginatedEksClusterRequest,
        live_events=EKS_CLUSTER_LIVE_EVENTS,
    ),
    ObjectKind.RDS_DB_INSTANCE: ExporterMetadata(
        RdsDbInstanceExporter,
        PaginatedDbInstanceRequest,
        live_events=RDS_DB_INSTANCE_LIVE_EVENTS,
    ),
    ObjectKind.RDS_DB_CLUSTER: ExporterMetadata(
        RdsDbClusterExporter,
        PaginatedDbClusterRequest,
        live_events=RDS_DB_CLUSTER_LIVE_EVENTS,
    ),
    ObjectKind.LAMBDA_FUNCTION: ExporterMetadata(
        LambdaFunctionExporter,
        PaginatedLambdaFunctionRequest,
        live_events=LAMBDA_FUNCTION_LIVE_EVENTS,
    ),
    ObjectKind.ECS_SERVICE: ExporterMetadata(
        EcsServiceExporter, PaginatedServiceRequest
    ),
    ObjectKind.ECS_TASK_DEFINITION: ExporterMetadata(
        EcsTaskDefinitionExporter, PaginatedTaskDefinitionRequest
    ),
    ObjectKind.SQS_QUEUE: ExporterMetadata(
        SqsQueueExporter,
        PaginatedQueueRequest,
        live_events=SQS_QUEUE_LIVE_EVENTS,
    ),
    ObjectKind.ECR_REPOSITORY: ExporterMetadata(
        EcrRepositoryExporter,
        PaginatedRepositoryRequest,
        live_events=ECR_REPOSITORY_LIVE_EVENTS,
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
        ElastiCacheClusterExporter,
        PaginatedCacheClusterRequest,
        live_events=ELASTICACHE_CLUSTER_LIVE_EVENTS,
    ),
    ObjectKind.EC2_VOLUME: ExporterMetadata(
        EbsVolumeExporter,
        PaginatedEbsVolumeRequest,
        live_events=EC2_VOLUME_LIVE_EVENTS,
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
        SesEmailIdentityExporter,
        PaginatedEmailIdentityRequest,
        live_events=SES_EMAIL_IDENTITY_LIVE_EVENTS,
    ),
    ObjectKind.DYNAMODB_TABLE: ExporterMetadata(
        DynamoDBTableExporter,
        PaginatedTableRequest,
        live_events=DYNAMODB_TABLE_LIVE_EVENTS,
    ),
    ObjectKind.SES_CONFIGURATION_SET: ExporterMetadata(
        SesConfigurationSetExporter,
        PaginatedConfigurationSetRequest,
        live_events=SES_CONFIGURATION_SET_LIVE_EVENTS,
    ),
    ObjectKind.SNS_TOPIC: ExporterMetadata(
        SNSTopicExporter,
        PaginatedTopicRequest,
        live_events=SNS_TOPIC_LIVE_EVENTS,
    ),
}
