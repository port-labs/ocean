from pydantic import Field
from aws.core.exporters.ecs.base_options import ExporterOptions


class SingleECSClusterExporterOptions(ExporterOptions):
    """Options for exporting a single ECS cluster."""

    cluster_arn: str = Field(..., description="The ARN of the ECS cluster to export")


class PaginatedECSClusterExporterOptions(ExporterOptions): ...
