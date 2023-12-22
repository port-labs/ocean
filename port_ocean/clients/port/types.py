from enum import Enum
from typing import TypedDict


class UserAgentType(Enum):
    exporter = "exporter"
    gitops = "gitops"


KafkaCreds = TypedDict(
    "KafkaCreds",
    {
        "username": str,
        "password": str,
    },
)

RequestOptions = TypedDict(
    "RequestOptions",
    {
        "merge": bool,
        "create_missing_related_entities": bool,
        "delete_dependent_entities": bool,
        "validation_only": bool,
    },
)
