from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectIdentifier(BaseModel):
    """Identifies a Foundry project for project-scoped exporters."""

    project_endpoint: str
    project_id: str


class ListAgentsOptions(ProjectIdentifier):
    include_versions: bool = False


class ListModelDeploymentsOptions(ProjectIdentifier):
    pass


class ListConversationsOptions(ProjectIdentifier):
    since_days: int | None = Field(default=30)


class ListResponsesOptions(ProjectIdentifier):
    since_days: int | None = Field(default=30)


class ListMemoryStoresOptions(ProjectIdentifier):
    pass
