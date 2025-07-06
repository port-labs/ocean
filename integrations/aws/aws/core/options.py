from pydantic import BaseModel, Field
from typing import Literal, Optional, TypeAlias


class ExporterOptions(BaseModel):
    region: str = Field(..., description="The AWS region to export resources from")
    method: str = Field(..., description="The method to export resources from")
    max_results: Optional[int] = Field(
        default=100,
        ge=10,
        le=1000,
        description="The maximum number of results to return",
    )


class SingleSQSQueueExporterOptions(ExporterOptions):
    queue_url: str = Field(..., description="The URL of the SQS queue to export")
    attribute_names: list[
        Literal[
            "All",
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesDelayed",
            "ApproximateNumberOfMessagesNotVisible",
            "CreatedTimestamp",
            "DelaySeconds",
            "LastModifiedTimestamp",
            "MaximumMessageSize",
            "MessageRetentionPeriod",
            "Policy",
            "ReceiveMessageWaitTimeSeconds",
            "VisibilityTimeout",
        ]
    ] = Field(default=["All"], description="The attributes to export")


class ListSQSExporterOptions(ExporterOptions):
    queue_name_prefix: Optional[str] = Field(
        default=None, description="The prefix of the queue name to export"
    )


class ListGroupResourcesEnricherOptions(ExporterOptions):
    group: str = Field(
        ...,
        description="The name or the Amazon resource name (ARN) of the resource group.",
    )


class SingleResourceGroupExporterOptions(ExporterOptions):
    group: str = Field(..., description="The name of the resource group to export")
    include: Optional[ListGroupResourcesEnricherOptions] = Field(
        default=None,
        description="The resources to include in the export",
    )


class ListResourceGroupExporterOptions(ExporterOptions):
    include: Literal["resources"] = Field(
        default="resources",
        description="The resources to include in the export",
    )


class ListS3BucketsExporterOptions(ExporterOptions): ...


class SingleS3BucketExporterOptions(ExporterOptions):
    bucket: str = Field(..., description="The name of the S3 bucket to export")


SupportedServices: TypeAlias = Literal["sqs", "resource-groups", "s3"]
