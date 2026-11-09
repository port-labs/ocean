from __future__ import annotations

from typing import NotRequired, Required, TypedDict


class ProjectIdentifier(TypedDict):
    """Identifies a Foundry project for project-scoped exporters."""

    project_endpoint: Required[str]
    project_id: Required[str]


class ListAgentsOptions(ProjectIdentifier):
    include_versions: NotRequired[bool]


class ListModelDeploymentsOptions(ProjectIdentifier):
    pass


class ListConversationsOptions(ProjectIdentifier):
    since_days: NotRequired[int | None]


class ListResponsesOptions(ProjectIdentifier):
    since_days: NotRequired[int | None]


class ListMemoryStoresOptions(ProjectIdentifier):
    pass
