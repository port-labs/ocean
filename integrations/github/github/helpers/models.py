from typing import TypedDict
from pydantic.v1 import BaseModel, Field


class RepoSearchParams(BaseModel):
    query: str = Field(
        title="Query",
        default_factory=str,
        description="GitHub repository search query (e.g. 'org:myorg' or 'topic:security').",
    )


class AlertRepository(TypedDict, total=False):
    """Nested ``repository`` object on org-level security alert payloads."""

    name: str
    archived: bool


class SecurityAlert(TypedDict, total=False):
    """Fields this helper reads from GitHub alerts or writes during enrichment.

    Other alert keys (``number``, ``state``, ``rule``, …) are passed through
    untouched; they are intentionally omitted here.
    """

    repository: AlertRepository
    __repository: str
    __organization: str
