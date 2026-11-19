from typing import Required, TypedDict


class ListPromptOptions(TypedDict, total=False):
    from_updated_at: str | None
    label: str | None
    tag: str | None


class SinglePromptOptions(TypedDict):
    name: Required[str]


class SingleDatasetOptions(TypedDict):
    name: Required[str]


class SingleModelOptions(TypedDict):
    model_id: Required[str]


class ListSessionOptions(TypedDict, total=False):
    from_start_time: str | None
    lookback_days: int


class SingleSessionOptions(TypedDict, total=False):
    session_id: Required[str]
    lookback_days: int
