from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EndpointScope = Literal["agent", "project"]


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
    endpoint_scopes: list[EndpointScope] = Field(default=["agent"])


class ListResponsesOptions(ProjectIdentifier):
    since_days: int | None = Field(default=30)
    endpoint_scopes: list[EndpointScope] = Field(default=["agent"])


class ListMemoryStoresOptions(ProjectIdentifier):
    pass
