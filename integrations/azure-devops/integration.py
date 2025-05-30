from pydantic import Field, BaseModel, validator
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.integrations.base import BaseIntegration

from azure_devops.gitops.file_entity_processor import GitManipulationHandler

from typing import List, Literal, Optional, Union

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.utils.signal import signal_handler
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from azure_devops.misc import AzureDevopsFolderResourceConfig


class AzureDevopsProjectResourceConfig(ResourceConfig):
    class AzureDevopsSelector(Selector):
        query: str
        default_team: bool = Field(
            default=False,
            description="If set to true, it ingests default team for each project to Port. This causes latency while syncing the entities to Port.  Default value is false. ",
            alias="defaultTeam",
        )

    kind: Literal["project"]
    selector: AzureDevopsSelector


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
        - "src/config.yaml"
        - "deployment/helm/values.yaml"
        - "config/settings.json"
        - ".github/workflows/ci.yml"
        - "docs/README.md"
        - "src/main.py"
        - "images/logo.png"

        Invalid paths:
        - "*" : glob patterns not allowed
        - "*.yaml" : glob patterns not allowed
        - "src/*.js" : glob patterns not allowed
        - "config/**/*.yaml" : glob patterns not allowed
        - "**/*" : glob patterns not allowed
        - "**" : glob patterns not allowed

        Each path must be an explicit file path relative to the repository root.
        Glob patterns are not supported to prevent overly broad file fetching.
        """,
    )
    repos: Optional[List[str]] = Field(
        default=None,
        description="List of repository names to scan. If None, scans all repositories.",
    )

    @validator("path", allow_reuse=True)
    def validate_path_patterns(cls, v: Union[str, List[str]]) -> Union[str, List[str]]:
        patterns = [v] if isinstance(v, str) else v

        if not patterns:
            raise ValueError("At least one file path must be specified")

        invalid_chars = {"*", "?", "[", "]", "{", "}", "**"}
        valid_paths = []

        for path in patterns:
            # Skip empty paths
            if not path or not path.strip():
                continue

            # Remove leading/trailing slashes and spaces
            cleaned_path = path.strip().strip("/")

            # Check for invalid glob characters
            if any(char in cleaned_path for char in invalid_chars):
                raise ValueError(
                    f"Path '{path}' contains glob patterns which are not allowed. "
                    "Please provide explicit file paths like 'src/config.yaml' or 'docs/README.md'"
                )

            valid_paths.append(cleaned_path)

        if not valid_paths:
            raise ValueError(
                "No valid file paths provided. Please provide explicit file paths "
                "like 'src/config.yaml' or 'docs/README.md'"
            )

        return valid_paths


class AzureDevopsFileSelector(Selector):
    """Selector for Azure DevOps file resources."""

    files: FilePattern = Field(
        description="""Configuration for file selection and scanning.

        Specify explicit file paths to fetch from repositories.
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
