from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_models import ResourceRequestModel


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
    deletion_identifier_properties_factory: Callable[
        [LiveEventContext], dict[str, str]
    ]


@dataclass
class ExporterMetadata:
    exporter: type[IResourceExporter[Any]]
    paginated_request_model: type[ResourceRequestModel]
    regional: bool = True
    live_events: LiveEventFactories | None = None

    @property
    def supports_live_events(self) -> bool:
        return self.live_events is not None
