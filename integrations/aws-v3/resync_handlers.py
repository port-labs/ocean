from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from aws.auth.session_factory import (
    initialize_aws_account_sessions,
    clear_aws_account_sessions,
    get_all_account_sessions,
)

from aws.core.helpers.types import ObjectKind
from resync import ResyncAWSService

# exporters
from aws.core.exporters.s3 import S3BucketExporter
from aws.core.exporters.s3.bucket.models import PaginatedBucketRequest
from aws.core.exporters.ec2.instance import EC2InstanceExporter, PaginatedEC2InstanceRequest
from aws.core.exporters.ecs.cluster.exporter import EcsClusterExporter
from aws.core.exporters.ecs.cluster.models import PaginatedClusterRequest
from aws.core.exporters.eks.cluster.exporter import EksClusterExporter
from aws.core.exporters.eks.cluster.models import PaginatedEksClusterRequest
from aws.core.exporters.rds.db_instance.exporter import RdsDbInstanceExporter
from aws.core.exporters.rds.db_instance.models import PaginatedDbInstanceRequest
from aws.core.exporters.ecs.service.exporter import EcsServiceExporter
from aws.core.exporters.ecs.service.models import PaginatedServiceRequest
from aws.core.exporters.ecs.task_definition.exporter import EcsTaskDefinitionExporter
from aws.core.exporters.ecs.task_definition.models import PaginatedTaskDefinitionRequest


# =========================
# LIFECYCLE HOOKS
# =========================

@ocean.on_resync_start()
async def initialize_aws_sessions() -> None:
    await initialize_aws_account_sessions()


@ocean.on_resync_complete()
async def cleanup_aws_sessions() -> None:
    await clear_aws_account_sessions()


# =========================
# RESYNC HANDLERS
# =========================

@ocean.on_resync(ObjectKind.S3_BUCKET)
async def resync_s3_bucket(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    service = ResyncAWSService(kind, S3BucketExporter, PaginatedBucketRequest, regional=False)
    async for batch in service:
        yield batch


@ocean.on_resync(ObjectKind.EC2_INSTANCE)
async def resync_ec2_instance(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    service = ResyncAWSService(kind, EC2InstanceExporter, PaginatedEC2InstanceRequest, regional=True)
    async for batch in service:
        yield batch


@ocean.on_resync(ObjectKind.ECS_CLUSTER)
async def resync_ecs_cluster(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    service = ResyncAWSService(kind, EcsClusterExporter, PaginatedClusterRequest, regional=True)
    async for batch in service:
        yield batch


@ocean.on_resync(ObjectKind.EKS_CLUSTER)
async def resync_eks_cluster(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    service = ResyncAWSService(kind, EksClusterExporter, PaginatedEksClusterRequest, regional=True)
    async for batch in service:
        yield batch


@ocean.on_resync(ObjectKind.RDS_DB_INSTANCE)
async def resync_rds_db_instance(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    service = ResyncAWSService(kind, RdsDbInstanceExporter, PaginatedDbInstanceRequest, regional=True)
    async for batch in service:
        yield batch


@ocean.on_resync(ObjectKind.ECS_SERVICE)
async def resync_ecs_service(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    service = ResyncAWSService(kind, EcsServiceExporter, PaginatedServiceRequest, regional=True)
    async for batch in service:
        yield batch


@ocean.on_resync(ObjectKind.ECS_TASK_DEFINITION)
async def resync_ecs_task_definition(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    service = ResyncAWSService(kind, EcsTaskDefinitionExporter, PaginatedTaskDefinitionRequest, regional=True)
    async for batch in service:
        yield batch


@ocean.on_resync(ObjectKind.AccountInfo)
async def resync_single_account(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    batch = []
    async for account, _ in get_all_account_sessions():
        batch.append({"Type": kind, "Properties": dict(account)})
        if len(batch) >= 100:
            yield batch
            batch = []
    if batch:
        yield batch