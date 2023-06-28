from enum import Enum
from typing import TypedDict, NotRequired


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
        "merge": NotRequired[bool],
        "create_missing_related_entities": NotRequired[bool],
        "delete_dependent_entities": NotRequired[bool],
        "validation_only": NotRequired[bool],
        "upsert": NotRequired[bool],
        "user_agent": NotRequired[str],
    },
)
