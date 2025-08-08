from pydantic import Field

from aws.core.exporters.s3.base_options import ExporterOptions


class SingleS3BucketExporterOptions(ExporterOptions):
    """Options for exporting a single S3 bucket."""

    bucket_name: str = Field(..., description="The name of the S3 bucket to export")


class PaginatedS3BucketExporterOptions(ExporterOptions): ...
