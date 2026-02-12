from typing import List, Literal, Optional, Union, Any
from datetime import datetime, timedelta, timezone

from pydantic import Field, BaseModel

from azure_devops.gitops.file_entity_processor import GitManipulationHandler
from azure_devops.misc import AzureDevopsFolderResourceConfig
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
    query: str
    default_team: bool = Field(
        default=False,
        description="If set to true, it ingests default team for each project to Port. This causes latency while syncing the entities to Port.  Default value is false. ",
        alias="defaultTeam",
    )


class AzureDevopsProjectResourceConfig(ResourceConfig):
    kind: Literal["project"]
    selector: AzureDevopsSelector


class AdvancedSecurityFilter(BaseModel):
    states: Optional[List[Literal["active", "dismissed", "fixed", "autoDismissed"]]] = (
        Field(
            alias="states",
            default=None,
            description="List of states to filter alerts by. If not provided, all states will be fetched.",
        )
    )
    severities: Optional[
        List[Literal["low", "medium", "high", "critical", "note", "warning", "error"]]
    ] = Field(
        alias="severity",
        default=None,
        description="List of severity levels to filter alerts by. If not provided, all severity levels will be fetched.",
    )
    alert_type: Optional[Literal["dependency", "code", "secret"]] = Field(
        default=None,
        alias="alertType",
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


class AzureDevopsAdvancedSecuritySelector(Selector):
    query: str
    criteria: Optional[AdvancedSecurityFilter] = Field(
        default=None,
        description="Filter criteria for alerts. If not provided, all alerts will be fetched.",
    )


class AzureDevopsAdvancedSecurityResourceConfig(ResourceConfig):
    kind: Literal["advanced-security-alert"]
    selector: AzureDevopsAdvancedSecuritySelector


class AzureDevopsWorkItemResourceConfig(ResourceConfig):
    class AzureDevopsSelector(Selector):
        query: str
        wiql: str | None = Field(
            default=None,
            description="WIQL query to filter work items. If not provided, all work items will be fetched.",
            alias="wiql",
        )
        expand: Literal["None", "Fields", "Relations", "Links", "All"] = Field(
            default="All",
            description="Expand options for work items. Allowed values are 'None', 'Fields', 'Relations', 'Links' and 'All'. Default value is 'All'.",
        )

    kind: Literal["work-item"]
    selector: AzureDevopsSelector


class FilePattern(BaseModel):
    """Configuration for file selection in Azure DevOps repositories."""

    path: Union[str, List[str]] = Field(
        ...,  # Make path required
        description="""
        Explicit file path(s) to fetch. Can be a single path or list of paths.

        Examples of valid paths:
        Literal Paths:
        - "src/config.yaml"
        - "deployment/helm/values.yaml"
        - "config/settings.json"
        - ".github/workflows/ci.yml"
        - "docs/README.md"
        - "src/main.py"
        - "images/logo.png"

        Glob patterns:
        - "*"
        - "*.yaml"
        - "src/*.js"
        - "config/**/*.yaml"
        - "**/*"
        - "**"

        Each path can be an explicit file path relative to the repository root or a glob pattern.
        """,
    )
    repos: Optional[List[str]] = Field(
        default=None,
        description="List of repository names to scan. If None, scans all repositories.",
    )


class AzureDevopsFileSelector(Selector):
    """Selector for Azure DevOps file resources."""

    files: FilePattern = Field(
        description="""Configuration for file selection and scanning.

        Specify file paths to fetch from repositories.
        Example:
        ```yaml
        selector:
          files:
            path:
              - "port.yml"
              - "config/settings.json"
              - ".github/workflows/ci.yml"
            repos:  # optional, if not specified will scan all repositories
              - "my-repo-1"
              - "my-repo-2"
        ```
        """,
    )


class AzureDevopsFileResourceConfig(ResourceConfig):
    kind: Literal["file"]
    selector: AzureDevopsFileSelector


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        default=False,
        description="Whether to include the members of the team, defaults to false",
    )


class AzureDevopsTeamResourceConfig(ResourceConfig):
    kind: Literal["team"]
    selector: TeamSelector


class AzureDevopsPipelineSelector(Selector):
    include_repo: bool = Field(
        default=False,
        alias="includeRepo",
        description="Whether to include the repository for each pipeline, defaults to false",
    )


class AzureDevopsPipelineResourceConfig(ResourceConfig):
    kind: Literal["pipeline"]
    selector: AzureDevopsPipelineSelector


class CodeCoverageConfig(BaseModel):
    flags: int | None = Field(
        default=None,
        alias="flags",
        description="Flags to control how detailed the coverage response will be",
    )


class AzureDevopsTestRunSelector(Selector):
    include_results: bool = Field(
        default=True,
        alias="includeResults",
        description="Whether to include test results for each test run, defaults to true",
    )
    code_coverage: Optional[CodeCoverageConfig] = Field(
        default=None,
        alias="codeCoverage",
        description="Whether to include code coverage data for each test run, defaults to None",
    )


class AzureDevopsTestRunResourceConfig(ResourceConfig):
    kind: Literal["test-run"]
    selector: AzureDevopsTestRunSelector


class AzureDevopsPullRequestSelector(Selector):
    min_time_in_days: int = Field(
        default=7,
        ge=1,
        alias="minTimeInDays",
        description="Minimum time in days since the pull request was abandoned or closed. Default value is 7.",
    )
    max_results: int = Field(
        default=100,
        ge=1,
        alias="maxResults",
        description="Maximum number of closed pull requests to fetch. Default value is 100.",
    )

    @property
    def min_time_datetime(self) -> datetime:
        """Convert the min time in days to a timezone-aware datetime object."""
        return datetime.now(timezone.utc) - timedelta(days=self.min_time_in_days)


class AzureDevopsPullRequestResourceConfig(ResourceConfig):
    kind: Literal["pull-request"]
    selector: AzureDevopsPullRequestSelector


class GitPortAppConfig(PortAppConfig):
    spec_path: List[str] | str = Field(alias="specPath", default="port.yml")
    use_default_branch: bool | None = Field(
        default=None,
        description=(
            "If set to true, it uses default branch of the repository"
            " for syncing the entities to Port. If set to false or None"
            ", it uses the branch mentioned in the `branch` config pro"
            "perty."
        ),
        alias="useDefaultBranch",
    )
    branch: str = "main"
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
        | ResourceConfig
    ] = Field(default_factory=list)


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
