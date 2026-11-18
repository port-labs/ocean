"""Factory Environments API models.

See https://docs.factory.com/api-reference/environments
"""

from __future__ import annotations

from pydantic.v1 import BaseModel, Field

from factory_ai.core.models import FactoryModel


class ListEnvironmentOptions(BaseModel):
    """Options for ``GET /api/v0/environments``.

    ``service_account_id`` maps to the optional ``serviceAccountId`` query param.
    """

    service_account_id: str | None = None

    def to_query_params(self) -> dict[str, str]:
        if not self.service_account_id:
            return {}
        return {"serviceAccountId": self.service_account_id}


class GetEnvironmentOptions(BaseModel):
    environment_id: str


class EnvironmentRepository(FactoryModel):
    url: str
    script: str


class EnvironmentProvider(FactoryModel):
    id: str
    name: str


class EnvironmentSource(FactoryModel):
    id: str
    name: str
    supports_repositories: bool = Field(alias="supportsRepositories")
    supports_setup_scripts: bool = Field(alias="supportsSetupScripts")
    provider: EnvironmentProvider
    unavailable: bool | None = None


class EnvironmentBuildRepository(FactoryModel):
    url: str
    name: str
    default_branch: str = Field(alias="defaultBranch")
    commit_sha: str = Field(alias="commitSha")


class EnvironmentLatestBuild(FactoryModel):
    id: str
    truncated: bool
    withheld: bool
    created_at: float = Field(alias="createdAt")
    status: str | None = None
    trigger: str | None = None
    repositories: list[EnvironmentBuildRepository] | None = None
    failure_reason: str | None = Field(None, alias="failureReason")
    failure_category: str | None = Field(None, alias="failureCategory")
    excerpt: str | None = None
    started_at: float | None = Field(None, alias="startedAt")
    finished_at: float | None = Field(None, alias="finishedAt")
    promoted_at: float | None = Field(None, alias="promotedAt")


class EnvironmentRepositoryCheckout(FactoryModel):
    repo_url: str = Field(alias="repoUrl")
    path: str


class Environment(FactoryModel):
    id: str
    name: str
    repositories: list[EnvironmentRepository]
    source: EnvironmentSource
    created_at: float = Field(alias="createdAt")
    updated_at: float = Field(alias="updatedAt")
    scope: str | None = None
    status: str | None = None
    is_default: bool | None = Field(None, alias="isDefault")
    active_repositories: list[EnvironmentRepository] | None = Field(
        None, alias="activeRepositories"
    )
    setup_script: str | None = Field(None, alias="setupScript")
    active_source: EnvironmentSource | None = Field(None, alias="activeSource")
    latest_build: EnvironmentLatestBuild | None = Field(None, alias="latestBuild")
    last_successful_build_at: float | None = Field(None, alias="lastSuccessfulBuildAt")
    failure_reason: str | None = Field(None, alias="failureReason")
    active_repository_checkouts: list[EnvironmentRepositoryCheckout] | None = Field(
        None, alias="activeRepositoryCheckouts"
    )


class ListEnvironmentsResponse(FactoryModel):
    environments: list[Environment]
    default_environment_id: str | None = Field(None, alias="defaultEnvironmentId")
    hidden_organization_environment_count: float | None = Field(
        None, alias="hiddenOrganizationEnvironmentCount"
    )
