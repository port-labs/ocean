from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CloudTrailEventAction(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


@dataclass(frozen=True)
class EventNameMapping:
    kind: str
    action: CloudTrailEventAction
    extract_identifier: Callable[[dict[str, Any]], str | None]
