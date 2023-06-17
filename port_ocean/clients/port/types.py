from typing import TypedDict, NotRequired

Headers = TypedDict(
    "Headers",
    {
        "Authorization": str,
        "User-Agent": str,
    },
)
KafkaCreds = TypedDict(
    "KafkaCreds",
    {
        "username": str,
        "password": str,
    },
)
ChangelogDestination = TypedDict(
    "ChangelogDestination",
    {"type": str, "url": NotRequired[str]},
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
