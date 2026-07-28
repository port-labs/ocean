from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aws.core.modeling.resource_models import ResourceRequestModel
from aws.webhook.cloudtrail_parser import NormalizedEvent


@dataclass(frozen=True)
class ExporterBinding:
    kind: str
    exporter_cls: type[Any]
    request_factory: Callable[[NormalizedEvent, list[str]], ResourceRequestModel]
    delete_properties_factory: Callable[[NormalizedEvent], dict[str, str]]
