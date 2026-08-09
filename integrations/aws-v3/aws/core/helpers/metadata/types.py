from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypedDict

from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel


class CloudTrailDetail(TypedDict, total=False):
    """CloudTrail record nested inside an EventBridge envelope."""

    eventName: str
    errorCode: str
    errorMessage: str
    awsRegion: str
    recipientAccountId: str
    requestParameters: dict[str, Any]


class EventBridgeCloudTrailPayload(TypedDict, total=False):
    """EventBridge envelope for ``AWS API Call via CloudTrail`` events."""

    account: str
    region: str
    detail: CloudTrailDetail


class CloudTrailEventAction(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


@dataclass(frozen=True)
class CloudTrailEventMapping:
    action: CloudTrailEventAction
    extract_identifier: Callable[[CloudTrailDetail], str | None]


@dataclass(frozen=True)
class EventNameMapping:
    kind: str
    action: CloudTrailEventAction
    extract_identifier: Callable[[CloudTrailDetail], str | None]


@dataclass(frozen=True)
class LiveEventContext:
    identifier: str
    account_id: str
    region: str


@dataclass(frozen=True)
class LiveEventFactories:
    """Factories for CloudTrail live-event handling."""

    request_factory: Callable[[LiveEventContext, list[str]], ResourceRequestModel]
    # Properties that identify the entity in Port when emitting deleted_raw_results
    deletion_identifier_properties_factory: Callable[[LiveEventContext], dict[str, str]]
    cloudtrail_mappings: dict[str, CloudTrailEventMapping] = field(default_factory=dict)


@dataclass
class ExporterMetadata:
    exporter: type[IResourceExporter[Any]]
    paginated_request_model: type[ResourceRequestModel]
    regional: bool = True
    live_events: LiveEventFactories | None = None
