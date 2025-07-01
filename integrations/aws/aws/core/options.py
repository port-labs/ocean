from pydantic import BaseModel
from typing import Literal, Optional, TypeAlias


class ExporterOptions(BaseModel):
    region: str
    max_results: Optional[int] = 100


class SingleSQSQueueOptions(ExporterOptions):
    queue_url: str
    method_name: str = "get_queue_attributes"
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
    ] = ["All"]


class ListSQSOptions(ExporterOptions):
    list_param: str = "QueueUrls"
    method_name: str = "list_queues"
    queue_name_prefix: Optional[str]


SupportedServices: TypeAlias = Literal["sqs",]
