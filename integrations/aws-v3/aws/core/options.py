from pydantic import BaseModel, Field
from typing import Literal, Optional, TypeAlias


class ExporterOptions(BaseModel):
    region: str = Field(..., description="The AWS region to export resources from")
    include: Optional[list[str]] = Field(
        default=None,
        description="The resources to include in the export",
    )


class SingleS3BucketExporterOptions(ExporterOptions):
    """Options for exporting a single S3 bucket."""

    bucket_name: str = Field(..., description="The name of the S3 bucket to export")


class PaginatedS3BucketExporterOptions(ExporterOptions): ...


SupportedServices: TypeAlias = Literal["sqs", "resource-groups", "s3", "ec2"]
