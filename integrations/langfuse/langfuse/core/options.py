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
