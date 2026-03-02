from typing import List, Literal, Optional, Union, Any
from datetime import datetime, timedelta, timezone

from pydantic import Field, BaseModel

from azure_devops.gitops.file_entity_processor import GitManipulationHandler
from azure_devops.misc import AzureDevopsFolderResourceConfig, Kind
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.utils.signal import signal_handler


class AzureDevopsSelector(Selector):
    default_team: bool = Field(
        default=False,
        title="Default Team",
        description="If set to true, it ingests default team for each project to Port. This causes latency while syncing the entities to Port.  Default value is false. ",
        alias="defaultTeam",
    )


class AzureDevopsProjectResourceConfig(ResourceConfig):
    kind: Literal["project"] = Field(
        title="Azure Devops Project",
        description="Azure Devops project resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Project selector",
        description="Selector for the project resource.",
    )


class AdvancedSecurityFilter(BaseModel):
    states: Optional[List[Literal["active", "dismissed", "fixed", "autoDismissed"]]] = (
        Field(
            alias="states",
            default=None,
            title="States",
            description="List of states to filter alerts by. If not provided, all states will be fetched.",
        )
    )
    severities: Optional[
        List[Literal["low", "medium", "high", "critical", "note", "warning", "error"]]
    ] = Field(
        alias="severity",
        default=None,
        title="Severities",
        description="List of severity levels to filter alerts by. If not provided, all severity levels will be fetched.",
    )
    alert_type: Optional[Literal["dependency", "code", "secret"]] = Field(
        default=None,
        alias="alertType",
        title="Alert Type",
        description="Type of alerts to filter by. If not provided, all alerts will be fetched.",
    )

    @property
    def as_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"criteria": {}}
        if self.states:
            params["criteria"]["states"] = ",".join(self.states)
        if self.severities:
            params["criteria"]["severity"] = ",".join(self.severities)
        if self.alert_type:
            params["criteria"]["alertType"] = self.alert_type
        return params

    class Config:
        extra = "forbid"


class AzureDevopsAdvancedSecuritySelector(Selector):
    criteria: Optional[AdvancedSecurityFilter] = Field(
        default=None,
        title="Criteria",
        description="Filter criteria for alerts. If not provided, all alerts will be fetched.",
    )


class AzureDevopsAdvancedSecurityResourceConfig(ResourceConfig):
    kind: Literal["advanced-security-alert"] = Field(
        title="Azure Devops Advanced Security Alert",
        description="Azure Devops advanced security alert resource kind.",
    )
    selector: AzureDevopsAdvancedSecuritySelector = Field(
        title="Advanced security alert selector",
        description="Selector for the advanced security alert resource.",
    )


class AzureDevopsWorkItemResourceConfig(ResourceConfig):
    class AzureDevopsSelector(Selector):
        wiql: str | None = Field(
            default=None,
            title="WIQL",
            description="WIQL query to filter work items. If not provided, all work items will be fetched.",
            alias="wiql",
        )
        expand: Literal["None", "Fields", "Relations", "Links", "All"] = Field(
            default="All",
            title="Expand",
            description="Expand options for work items. Allowed values are 'None', 'Fields', 'Relations', 'Links' and 'All'. Default value is 'All'.",
        )

    kind: Literal["work-item"] = Field(
        title="Azure Devops Work Item",
        description="Azure Devops work item resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Work item selector",
        description="Selector for the work item resource.",
    )


class FilePattern(BaseModel):
    path: Union[str, List[str]] = Field(
        title="Path",
        description="Explicit file path(s) to fetch, Can be a single path or a list of paths. For further details, <a target='_blank' href='https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/git/azure-devops/examples/#mapping-files'>Check our docs</a>.",
    )
    repos: Optional[List[str]] = Field(
        default=None,
        title="Repositories",
        description="List of repository names to scan. If None, scans all repositories.",
    )

    class Config:
        extra = "forbid"


class AzureDevopsFileSelector(Selector):
    files: FilePattern = Field(
        title="Files",
        description="Configuration for file selection and scanning.",
    )
    included_files: list[str] = Field(
        alias="includedFiles",
        default_factory=list,
        description="List of file paths to fetch and attach to the file entity",
    )


class AzureDevopsFileResourceConfig(ResourceConfig):
    kind: Literal["file"] = Field(
        title="Azure Devops File",
        description="Azure Devops file resource kind.",
    )
    selector: AzureDevopsFileSelector = Field(
        title="File selector",
        description="Selector for the file resource.",
    )


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        default=False,
        title="Include Members",
        description="Whether to include the members of the team, defaults to false",
    )


class AzureDevopsTeamResourceConfig(ResourceConfig):
    kind: Literal["team"] = Field(
        title="Azure Devops Team",
        description="Azure Devops team resource kind.",
    )
    selector: TeamSelector = Field(
        title="Team selector",
        description="Selector for the team resource.",
    )


class AzureDevopsPipelineSelector(Selector):
    include_repo: bool = Field(
        default=False,
        alias="includeRepo",
        title="Include Repository",
        description="Whether to include the repository for each pipeline, defaults to false",
    )


class AzureDevopsPipelineResourceConfig(ResourceConfig):
    kind: Literal["pipeline"] = Field(
        title="Azure Devops Pipeline",
        description="Azure Devops pipeline resource kind.",
    )
    selector: AzureDevopsPipelineSelector = Field(
        title="Pipeline selector",
        description="Selector for the pipeline resource.",
    )


class CodeCoverageConfig(BaseModel):
    flags: int | None = Field(
        default=None,
        alias="flags",
        title="Flags",
        description="Flags to control how detailed the coverage response will be",
    )

    class Config:
        extra = "forbid"


class AzureDevopsTestRunSelector(Selector):
    include_results: bool = Field(
        default=True,
        alias="includeResults",
        title="Include Results",
        description="Whether to include test results for each test run, defaults to true",
    )
    code_coverage: Optional[CodeCoverageConfig] = Field(
        default=None,
        alias="codeCoverage",
        title="Code Coverage",
        description="Whether to include code coverage data for each test run, defaults to None",
    )


class AzureDevopsTestRunResourceConfig(ResourceConfig):
    kind: Literal["test-run"] = Field(
        title="Azure Devops Test Run",
        description="Azure Devops test run resource kind.",
    )
    selector: AzureDevopsTestRunSelector = Field(
        title="Test run selector",
        description="Selector for the test run resource.",
    )


class AzureDevopsPullRequestSelector(Selector):
    min_time_in_days: int = Field(
        default=7,
        ge=1,
        alias="minTimeInDays",
        title="Minimum Time in Days",
        description="Minimum time in days since the pull request was abandoned or closed.",
    )
    max_results: int = Field(
        default=100,
        ge=1,
        alias="maxResults",
        title="Maximum Results",
        description="Maximum number of closed pull requests to fetch.",
    )

    @property
    def min_time_datetime(self) -> datetime:
        """Convert the min time in days to a timezone-aware datetime object."""
        return datetime.now(timezone.utc) - timedelta(days=self.min_time_in_days)


class AzureDevopsPullRequestResourceConfig(ResourceConfig):
    kind: Literal["pull-request"] = Field(
        title="Azure Devops Pull Request",
        description="Azure Devops pull request resource kind.",
    )
    selector: AzureDevopsPullRequestSelector = Field(
        title="Pull request selector",
        description="Selector for the pull request resource.",
    )


class AzureDevopsRepositorySelector(Selector):
    included_files: list[str] = Field(
        alias="includedFiles",
        default_factory=list,
        title="Included Files",
        description=(
            "List of file paths to fetch from the repository and attach to "
            "the raw data under __includedFiles. E.g. ['README.md', 'CODEOWNERS']"
        ),
    )


class AzureDevopsRepositoryResourceConfig(ResourceConfig):
    kind: Literal["repository"] = Field(
        title="Azure Devops Repository",
        description="Azure Devops repository resource kind.",
    )
    selector: AzureDevopsRepositorySelector = Field(
        title="Repository selector",
        description="Selector for the repository resource.",
    )


class AzureDevopsUserConfig(ResourceConfig):
    kind: Literal[Kind.USER] = Field(
        title="Azure Devops User",
        description="Azure Devops user resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="User selector",
        description="Selector for the user resource.",
    )


class AzureDevopsMemberConfig(ResourceConfig):
    kind: Literal[Kind.MEMBER] = Field(
        title="Azure Devops Member",
        description="Azure Devops member resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Member selector",
        description="Selector for the member resource.",
    )


class AzureDevopsBranchConfig(ResourceConfig):
    kind: Literal[Kind.BRANCH] = Field(
        title="Azure Devops Branch",
        description="Azure Devops branch resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Branch selector",
        description="Selector for the branch resource.",
    )


class AzureDevopsRepositoryPolicyConfig(ResourceConfig):
    kind: Literal[Kind.REPOSITORY_POLICY] = Field(
        title="Azure Devops Repository Policy",
        description="Azure Devops repository policy resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Repository policy selector",
        description="Selector for the repository policy resource.",
    )


class AzureDevopsBoardConfig(ResourceConfig):
    kind: Literal[Kind.BOARD] = Field(
        title="Azure Devops Board",
        description="Azure Devops board resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Board selector",
        description="Selector for the board resource.",
    )


class AzureDevopsColumnConfig(ResourceConfig):
    kind: Literal[Kind.COLUMN] = Field(
        title="Azure Devops Column",
        description="Azure Devops column resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Column selector",
        description="Selector for the column resource.",
    )


class AzureDevopsReleaseConfig(ResourceConfig):
    kind: Literal[Kind.RELEASE] = Field(
        title="Azure Devops Release",
        description="Azure Devops release resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Release selector",
        description="Selector for the release resource.",
    )


class AzureDevopsBuildConfig(ResourceConfig):
    kind: Literal[Kind.BUILD] = Field(
        title="Azure Devops Build",
        description="Azure Devops build resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Build selector",
        description="Selector for the build resource.",
    )


class AzureDevopsPipelineStageConfig(ResourceConfig):
    kind: Literal[Kind.PIPELINE_STAGE] = Field(
        title="Azure Devops Pipeline Stage",
        description="Azure Devops pipeline stage resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Pipeline stage selector",
        description="Selector for the pipeline stage resource.",
    )


class AzureDevopsPipelineRunConfig(ResourceConfig):
    kind: Literal[Kind.PIPELINE_RUN] = Field(
        title="Azure Devops Pipeline Run",
        description="Azure Devops pipeline run resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Pipeline run selector",
        description="Selector for the pipeline run resource.",
    )


class AzureDevopsEnvironmentConfig(ResourceConfig):
    kind: Literal[Kind.ENVIRONMENT] = Field(
        title="Azure Devops Environment",
        description="Azure Devops environment resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Environment selector",
        description="Selector for the environment resource.",
    )


class AzureDevopsReleaseDeploymentConfig(ResourceConfig):
    kind: Literal[Kind.RELEASE_DEPLOYMENT] = Field(
        default=Kind.RELEASE_DEPLOYMENT,
        description="Resource kind (release-deployment).",
    )
    selector: AzureDevopsSelector = Field(
        title="Release deployment selector",
        description="Selector for the release deployment resource.",
    )


class AzureDevopsPipelineDeploymentConfig(ResourceConfig):
    kind: Literal[Kind.PIPELINE_DEPLOYMENT] = Field(
        title="Azure Devops Pipeline Deployment",
        description="Resource kind (pipeline-deployment).",
    )
    selector: AzureDevopsSelector = Field(
        title="Pipeline deployment selector",
        description="Selector for the pipeline deployment resource.",
    )


class AzureDevopsIterationConfig(ResourceConfig):
    kind: Literal[Kind.ITERATION] = Field(
        title="Azure Devops Iteration",
        description="Azure Devops iteration resource kind.",
    )
    selector: AzureDevopsSelector = Field(
        title="Iteration selector",
        description="Selector for the iteration resource.",
    )


class AzureDevopsGroupMemberResourceConfig(ResourceConfig):
    kind: Literal["group-member"]


class GitPortAppConfig(PortAppConfig):
    spec_path: List[str] | str = Field(alias="specPath", default="port.yml")
    use_default_branch: bool | None = Field(
        default=None,
        alias="useDefaultBranch",
        title="Use Default Branch",
        description="If set to true, it uses default branch of the repository for syncing the entities to Port. If set to false or None, it uses the branch mentioned in the `branch` config property. Default value is None.",
    )
    branch: str = Field(
        default="main",
        title="Branch",
        description="Branch to use for syncing the entities to Port. Default value is 'main'.",
    )
    resources: list[
        AzureDevopsProjectResourceConfig
        | AzureDevopsFolderResourceConfig
        | AzureDevopsWorkItemResourceConfig
        | AzureDevopsTeamResourceConfig
        | AzureDevopsFileResourceConfig
        | AzureDevopsPipelineResourceConfig
        | AzureDevopsTestRunResourceConfig
        | AzureDevopsPullRequestResourceConfig
        | AzureDevopsAdvancedSecurityResourceConfig
        | AzureDevopsRepositoryResourceConfig
        | AzureDevopsUserConfig
        | AzureDevopsMemberConfig
        | AzureDevopsBranchConfig
        | AzureDevopsRepositoryPolicyConfig
        | AzureDevopsBoardConfig
        | AzureDevopsColumnConfig
        | AzureDevopsReleaseConfig
        | AzureDevopsBuildConfig
        | AzureDevopsPipelineStageConfig
        | AzureDevopsPipelineRunConfig
        | AzureDevopsEnvironmentConfig
        | AzureDevopsReleaseDeploymentConfig
        | AzureDevopsPipelineDeploymentConfig
        | AzureDevopsIterationConfig
        | AzureDevopsGroupMemberResourceConfig
    ] = Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations for the integration.",
    )  # type: ignore[assignment]


class AzureDevopsHandlerMixin(HandlerMixin):
    EntityProcessorClass = GitManipulationHandler


class AzureDevopsLiveEventsProcessorManager(
    LiveEventsProcessorManager, AzureDevopsHandlerMixin
):
    pass


class AzureDevopsIntegration(BaseIntegration, AzureDevopsHandlerMixin):
    def __init__(self, context: PortOceanContext):
        super().__init__(context)
        # Replace the Ocean's webhook manager with our custom one
        self.context.app.webhook_manager = AzureDevopsLiveEventsProcessorManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitPortAppConfig
