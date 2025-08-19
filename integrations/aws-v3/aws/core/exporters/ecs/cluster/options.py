from aws.core.exporters.ecs.cluster.models import (
    SingleECSClusterRequest,
    PaginatedECSClusterRequest,
)

# Re-export the request models for backward compatibility
SingleECSClusterExporterOptions = SingleECSClusterRequest
PaginatedECSClusterExporterOptions = PaginatedECSClusterRequest
