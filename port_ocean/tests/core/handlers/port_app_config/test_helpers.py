from typing import Any

from pydantic.v1 import Field


def resources_field() -> Any:
    return Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations for the integration.",
    )
