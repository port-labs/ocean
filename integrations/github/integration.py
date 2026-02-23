from datetime import datetime, timedelta, timezone
from fastapi import Request
from loguru import logger
from pydantic import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.exceptions.api import EmptyPortAppConfigError
from port_ocean.core.handlers.queue import GroupQueue
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    LiveEventTimestamp,
    WebhookEvent,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.utils.signal import signal_handler
from typing import Any, Dict, List, Optional, Type, Literal

from github.entity_processors.file_entity_processor import FileEntityProcessor
from github.helpers.models import RepoSearchParams
from github.helpers.utils import ObjectKind
from github.webhook.live_event_group_selector import get_primary_id
from github.helpers.port_app_config import (
    is_repo_managed_mapping,
    load_org_port_app_config,
)

FILE_PROPERTY_PREFIX = "file://"


class RepoSearchSelector(Selector):
    repo_search: Optional[RepoSearchParams] = Field(
        title="Repositories",
        alias="repoSearch",
        description="Ingest specific repositories using <a target='_blank' href='https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories'>Github repository search API</a>",
        default=None,
    )


class GithubRepositorySelector(RepoSearchSelector):
    include: Optional[List[Literal["collaborators", "teams", "sbom"]]] = Field(
        title="Additional Repository Data",
        description="Fetch additional data related to the repository. The accepted values are: <a target='_blank' href='https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/git/github-ocean/examples#:~:text=teams%20with%20access%20to%20the%20repository'>teams</a>, <a target='_blank' href='https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/git/github-ocean/examples#:~:text=collaborators%20of%20the%20repository'>collaborators</a>, <a target='_blank' href='https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/git/github-ocean/examples#:~:text=%3A%20Ingests%20the-,Software%20Bill%20of%20Materials%20(SBOM),-for%20the%20repository'>sbom</a>",
        default_factory=list,
    )
    included_files: list[str] = Field(
        title="Included Files",
        alias="includedFiles",
        default_factory=list,
        description=(
            "List of file paths to fetch from the repository and attach to "
            "the raw data under __includedFiles. E.g. ['README.md', 'CODEOWNERS']"
        ),
    )


class GithubRepositoryConfig(ResourceConfig):
    selector: GithubRepositorySelector = Field(
        title="Repository Selector",
        description="Selector for the repository resource.",
    )
    kind: Literal["repository"] = Field(
        title="Github Repository",
        description="Github repository resource kind.",
    )


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        title="Repository Name",
        description="The repository name to fetch from.",
    )
    branch: Optional[str] = Field(
        title="Branch",
        default=None,
        description="Branch to use; repo's default branch will be used if not specified.",
    )

    class Config:
        extra = "forbid"


class FolderSelector(BaseModel):
    organization: Optional[str] = Field(
        title="Organization",
        default=None,
        description="GitHub organization name.",
    )
    path: str = Field(
        title="Path",
        default="*",
        description="Glob path for folders (e.g. '*' or 'src/**').",
    )
    repos: Optional[list[RepositoryBranchMapping]] = Field(
        title="Repositories",
        description="Repositories and branches to fetch folders from.",
        default=None,
    )

    class Config:
        extra = "forbid"


class GithubFolderSelector(Selector):
    folders: list[FolderSelector] = Field(
        title="Folders",
        description="Folder definitions (path and repos) to ingest.",
    )
    included_files: list[str] = Field(
        title="Included Files",
        alias="includedFiles",
        default_factory=list,
        description="File paths to fetch and attach to the folder entity.",
    )


class GithubUserSelector(Selector):
    include_bots: bool = Field(
        title="Include Bots",
        default=True,
        alias="includeBots",
        description="Include bot accounts in the list of users.",
    )


class GithubUserConfig(ResourceConfig):
    selector: GithubUserSelector = Field(
        title="User selector",
        description="Selector for the user resource.",
    )
    kind: Literal[ObjectKind.USER] = Field(
        title="Github User",
        description="Github user resource kind.",
    )


class GithubFolderResourceConfig(ResourceConfig):
    selector: GithubFolderSelector = Field(
        title="Folder selector",
        description="Selector for the folder resource.",
    )
    kind: Literal[ObjectKind.FOLDER] = Field(
        title="Github Folder",
        description="Github folder resource kind.",
    )


class GithubPullRequestSelector(RepoSearchSelector):
    states: list[Literal["open", "closed"]] = Field(
        title="Pull requests states",
        default=["open"],
        description="Filter pull requests by states (e.g. ['open']).",
    )
    max_results: int = Field(
        title="Max pull requests to return",
        alias="maxResults",
        default=100,
        ge=1,
        description="Maximum number of pull requests to return per repository.",
    )
    since: int = Field(
        title="Since (Days)",
        default=60,
        ge=1,
        description="Only fetch pull requests updated within the last N days.",
    )
    api: Literal["rest", "graphql"] = Field(
        title="API",
        default="rest",
        description="API to use for fetching pull requests (REST or GraphQL).",
    )

    @property
    def updated_after(self) -> datetime:
        """Convert the since days to a timezone-aware datetime object."""
        return datetime.now(timezone.utc) - timedelta(days=self.since)


class GithubPullRequestConfig(ResourceConfig):
    selector: GithubPullRequestSelector = Field(
        title="Pull request selector",
        description="Selector for the pull request resource.",
    )
    kind: Literal["pull-request"] = Field(
        title="Github Pull Request",
        description="Github pull request resource kind.",
    )


class GithubIssueSelector(RepoSearchSelector):
    state: Literal["open", "closed", "all"] = Field(
        title="State",
        default="open",
        description="Filter by issue state (open, closed, or all).",
    )
    labels: Optional[list[str]] = Field(
        title="Labels",
        default=None,
        description="Filter issues by labels; issues must have ALL specified labels (e.g. ['bug', 'enhancement']).",
    )

    @property
    def labels_str(self) -> Optional[str]:
        """Convert labels list to comma-separated string for GitHub API."""
        return ",".join(self.labels) if self.labels else None


class GithubIssueConfig(ResourceConfig):
    selector: GithubIssueSelector = Field(
        title="Issue selector",
        description="Selector for the issue resource.",
    )
    kind: Literal["issue"] = Field(
        title="Github Issue",
        description="Github issue resource kind.",
    )


class GithubTeamSector(Selector):
    members: bool = Field(
        title="Include Members",
        default=True,
        description="Include team members in the exported data.",
    )


class GithubTeamConfig(ResourceConfig):
    selector: GithubTeamSector
    kind: Literal[ObjectKind.TEAM]


class GithubDependabotAlertSelector(RepoSearchSelector):
    states: list[Literal["auto_dismissed", "dismissed", "fixed", "open"]] = Field(
        title="States",
        description="Filter alerts by states (e.g. ['auto_dismissed', 'dismissed', 'fixed', 'open']).",
        default=["open"],
    )
    severity: Optional[list[Literal["low", "medium", "high", "critical"]]] = Field(
        title="Severity",
        description="Filter alerts by severity (e.g. ['low', 'medium']).",
        default=None,
    )
    ecosystems: Optional[
        list[
            Literal[
                "composer",
                "go",
                "maven",
                "npm",
                "nuget",
                "pip",
                "pub",
                "rubygems",
                "rust",
            ]
        ]
    ] = Field(
        title="Ecosystems",
        description="Filter alerts by package ecosystem (e.g. ['npm', 'pip']).",
        default=None,
    )

    @property
    def severity_str(self) -> Optional[str]:
        """Convert severity list to comma-separated string for GitHub API."""
        return ",".join(self.severity) if self.severity else None

    @property
    def ecosystems_str(self) -> Optional[str]:
        """Convert ecosystems list to comma-separated string for GitHub API."""
        return ",".join(self.ecosystems) if self.ecosystems else None


class GithubDependabotAlertConfig(ResourceConfig):
    selector: GithubDependabotAlertSelector = Field(
        title="Dependabot alert selector",
        description="Selector for the dependabot alert resource.",
    )
    kind: Literal["dependabot-alert"] = Field(
        title="Github Dependabot Alert",
        description="Github dependabot alert resource kind.",
    )


class GithubCodeScanningAlertSelector(RepoSearchSelector):
    state: Literal["open", "closed", "dismissed", "fixed"] = Field(
        title="State",
        description="Filter alerts by state (e.g. 'open', 'closed', 'dismissed', 'fixed').",
        default="open",
    )
    severity: Optional[
        Literal["critical", "high", "medium", "low", "warning", "note", "error"]
    ] = Field(
        title="Severity",
        description="Filter alerts by severity level (e.g. 'critical', 'high', 'medium', 'low', 'warning', 'note', 'error').",
        default=None,
    )


class GithubCodeScanningAlertConfig(ResourceConfig):
    selector: GithubCodeScanningAlertSelector = Field(
        title="Code scanning alert selector",
        description="Selector for the code scanning alert resource.",
    )
    kind: Literal["code-scanning-alerts"] = Field(
        title="Github Code Scanning Alert",
        description="Github code scanning alert resource kind.",
    )


class GithubDeploymentSelector(RepoSearchSelector):
    task: Optional[str] = Field(
        title="Task name",
        description="Filter deployments by task name (e.g. deploy, deploy:migrations).",
        default=None,
    )
    environment: Optional[str] = Field(
        title="Environment name",
        description="Filter deployments by environment name (e.g. staging, production).",
        default=None,
    )


class GithubDeploymentConfig(ResourceConfig):
    selector: GithubDeploymentSelector = Field(
        title="Deployment selector",
        description="Selector for the deployment resource.",
    )
    kind: Literal["deployment"] = Field(
        title="Github Deployment",
        description="Github deployment resource kind.",
    )


class GithubSecretScanningAlertSelector(RepoSearchSelector):
    state: Literal["open", "resolved", "all"] = Field(
        title="State",
        description="Filter alerts by state (open, resolved, all).",
        default="open",
    )
    hide_secret: bool = Field(
        title="Hide Secret",
        alias="hideSecret",
        description="Control whether the secret content is included.",
        default=True,
    )


class GithubSecretScanningAlertConfig(ResourceConfig):
    selector: GithubSecretScanningAlertSelector = Field(
        title="Secret scanning alert selector",
        description="Selector for the secret scanning alert resource.",
    )
    kind: Literal["secret-scanning-alerts"] = Field(
        title="Github Secret Scanning Alert",
        description="Github secret scanning alert resource kind.",
    )
    kind: Literal["secret-scanning-alerts"]


class GithubFilePattern(BaseModel):
    organization: Optional[str] = Field(
        title="Organization",
        default=None,
        description="GitHub organization (optional).",
    )
    path: str = Field(
        title="Path",
        alias="path",
        description="Glob path to match files (e.g. '**/*.yaml').",
    )
    repos: Optional[list[RepositoryBranchMapping]] = Field(
        title="Repositories",
        alias="repos",
        description="Repositories and branches to fetch files from.",
        default=None,
    )
    skip_parsing: bool = Field(
        title="Skip Parsing",
        default=False,
        alias="skipParsing",
        description="Return raw file content without parsing.",
    )
    validation_check: bool = Field(
        title="Validation Check",
        default=False,
        alias="validationCheck",
        description="Enable validation for this file pattern during pull request processing.",
    )

    class Config:
        extra = "forbid"


class GithubFileSelector(Selector):
    files: list[GithubFilePattern] = Field(
        title="Files",
        description="File patterns (path, repos) to ingest.",
    )
    included_files: list[str] = Field(
        title="Included Files",
        alias="includedFiles",
        default_factory=list,
        description="Additional file paths to fetch and attach to the file entity.",
    )


class GithubFileResourceConfig(ResourceConfig):
    kind: Literal["file"] = Field(
        title="Github File",
        description="Github file resource kind.",
    )
    selector: GithubFileSelector = Field(
        title="File selector",
        description="Selector for the file resource.",
    )


class GithubBranchSelector(RepoSearchSelector):
    detailed: bool = Field(
        title="Detailed",
        default=False,
        description="Whether to include the latest commit details for each branch.",
    )
    default_branch_only: bool = Field(
        title="Default Branch Only",
        default=False,
        alias="defaultBranchOnly",
        description="Sync only the repository's default branch; overrides branchNames if set.",
    )
    protection_rules: bool = Field(
        title="Protection Rules",
        default=False,
        alias="protectionRules",
        description="Whether to include branch protection rules for each branch.",
    )
    branch_names: List[str] = Field(
        title="Branch Names",
        default_factory=list,
        alias="branchNames",
        description="Branches to fetch (e.g. ['main', 'develop']).",
    )


class GithubBranchConfig(ResourceConfig):
    kind: Literal["branch"] = Field(
        title="Github Branch",
        description="Github branch resource kind.",
    )
    selector: GithubBranchSelector = Field(
        title="Branch selector",
        description="Selector for the branch resource.",
    )


class GithubOrganizationConfig(ResourceConfig):
    kind: Literal[ObjectKind.ORGANIZATION] = Field(
        title="Github Organization",
        description="Github organization resource kind.",
    )
    selector: RepoSearchSelector = Field(
        title="Organization selector",
        description="Selector for the organization resource.",
    )


class GithubWorkflowConfig(ResourceConfig):
    kind: Literal[ObjectKind.WORKFLOW] = Field(
        title="Github Workflow",
        description="Github workflow resource kind.",
    )
    selector: RepoSearchSelector = Field(
        title="Workflow selector",
        description="Selector for the workflow resource.",
    )


class GithubWorkflowRunConfig(ResourceConfig):
    kind: Literal[ObjectKind.WORKFLOW_RUN] = Field(
        title="Github Workflow Run",
        description="Github workflow run resource kind.",
    )
    selector: RepoSearchSelector = Field(
        title="Workflow run selector",
        description="Selector for the workflow run resource.",
    )


class GithubReleaseConfig(ResourceConfig):
    kind: Literal[ObjectKind.RELEASE] = Field(
        title="Github Release",
        description="Github release resource kind.",
    )
    selector: RepoSearchSelector = Field(
        title="Release selector",
        description="Selector for the release resource.",
    )


class GithubTagConfig(ResourceConfig):
    kind: Literal[ObjectKind.TAG] = Field(
        title="Github Tag",
        description="Github tag resource kind.",
    )
    selector: RepoSearchSelector = Field(
        title="Tag selector",
        description="Selector for the tag resource.",
    )


class GithubEnvironmentConfig(ResourceConfig):
    kind: Literal[ObjectKind.ENVIRONMENT] = Field(
        title="Github Environment",
        description="Github environment resource kind.",
    )
    selector: RepoSearchSelector = Field(
        title="Environment selector",
        description="Selector for the environment resource.",
    )


class GithubCollaboratorConfig(ResourceConfig):
    kind: Literal[ObjectKind.COLLABORATOR] = Field(
        title="Github Collaborator",
        description="Github collaborator resource kind.",
    )
    selector: RepoSearchSelector = Field(
        title="Collaborator selector",
        description="Selector for the collaborator resource.",
    )


class GithubPortAppConfig(PortAppConfig):
    organizations: List[str] = Field(
        title="Organizations",
        default_factory=list,
        description=(
            "List of GitHub organization names (optional - if not provided, "
            "will sync all organizations the personal access token user is a "
            "member of) for Classic PAT authentication."
        ),
    )
    include_authenticated_user: bool = Field(
        title="Include Authenticated User",
        default=False,
        alias="includeAuthenticatedUser",
        description="Include the authenticated user's personal account.",
    )
    repository_type: str = Field(
        title="Repository Type",
        alias="repositoryType",
        enum=["all", "public", "private"],
        default="all",
        description="Filter repositories by visibility.",
    )
    resources: list[
        GithubRepositoryConfig
        | GithubPullRequestConfig
        | GithubIssueConfig
        | GithubDependabotAlertConfig
        | GithubCodeScanningAlertConfig
        | GithubDeploymentConfig
        | GithubFolderResourceConfig
        | GithubTeamConfig
        | GithubFileResourceConfig
        | GithubBranchConfig
        | GithubSecretScanningAlertConfig
        | GithubUserConfig
        | GithubOrganizationConfig
        | GithubWorkflowConfig
        | GithubWorkflowRunConfig
        | GithubReleaseConfig
        | GithubTagConfig
        | GithubEnvironmentConfig
        | GithubCollaboratorConfig
    ] = Field(
        title="Resources",
        default_factory=list,
        description=("Resource mappings"),
    )


class GitManipulationHandler(JQEntityProcessor):
    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            logger.warning(
                f"DEPRECATION: Using 'file://' prefix in mappings is deprecated and will be removed in a future version. "
                f"Pattern: '{pattern}'. "
                f"Use the 'includedFiles' selector instead. Example: "
                f"selector.includedFiles: ['{pattern[len(FILE_PROPERTY_PREFIX):]}'] "
                f'and mapping: .__includedFiles["{pattern[len(FILE_PROPERTY_PREFIX):]}"]'
            )
            entity_processor = FileEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return await entity_processor(self.context)._search(data, pattern)


class GithubHandlerMixin(HandlerMixin):
    EntityProcessorClass = GitManipulationHandler


class GithubLiveEventsProcessorManager(LiveEventsProcessorManager, GithubHandlerMixin):
    pass


class GithubLiveEventsGroupProcessorManager(
    LiveEventsProcessorManager, GithubHandlerMixin
):
    def register_processor(
        self, path: str, processor: Type[AbstractWebhookProcessor]
    ) -> None:
        """Register a webhook processor for a specific path with optional filter

        Args:
            path: The webhook path to register
            processor: The processor class to register
            kind: The resource kind to associate with this processor, or None to match any kind
        """
        if not issubclass(processor, AbstractWebhookProcessor):
            raise ValueError("Processor must extend AbstractWebhookProcessor")

        if path not in self._processors_classes:
            self._processors_classes[path] = []
            self._event_queues[path] = GroupQueue(("group_id"))
            self._register_route(path)

        self._processors_classes[path].append(processor)

    def _register_route(self, path: str) -> None:
        async def handle_webhook(request: Request) -> Dict[str, str]:
            """Handle incoming webhook requests for a specific path."""
            try:
                webhook_event = await WebhookEvent.from_request(request)
                webhook_event.set_timestamp(LiveEventTimestamp.AddedToQueue)
                webhook_event.group_id = get_primary_id(webhook_event)
                await self._event_queues[path].put(webhook_event)
                return {"status": "ok"}
            except Exception as e:
                logger.exception(f"Error processing webhook: {str(e)}")
                return {"status": "error", "message": str(e)}

        self._router.add_api_route(
            path,
            handle_webhook,
            methods=["POST"],
        )


class GithubIntegration(BaseIntegration, GithubHandlerMixin):
    def __init__(self, context: PortOceanContext):
        logger.info("Initializing Github Integration")
        super().__init__(context)

        # Override the Ocean's default webhook manager with our custom one
        # This is necessary because we need GithubHandlerMixin which provides
        # GitManipulationHandler to handle file:// prefixed properties and enable
        # dynamic switching between JQEntityProcessor and FileEntityProcessor
        # for GitHub-specific file content processing.
        event_workers_count = context.config.event_workers_count
        ProcessManager = (
            GithubLiveEventsGroupProcessorManager
            if event_workers_count > 1
            else GithubLiveEventsProcessorManager
        )
        processor_manager = ProcessManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )
        self.context.app.webhook_manager = processor_manager
        self.context.app.execution_manager._webhook_manager = processor_manager

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GithubPortAppConfig

        async def _get_port_app_config(self) -> dict[str, Any]:
            """
            Retrieve the Port app config for the GitHub Ocean integration.

            - If `config.repoManagedMapping` is true, ignore the API mapping
              and load the Port app config from a GitHub organization config
              repository (global mapping).
            - Otherwise, if `config` is non-empty, use it as-is (standard mapping).
            - If `config` is empty and no repo source is specified, treat it as an
              invalid/empty mapping.
            """
            logger.info("Fetching GitHub Port app config")

            integration = await self.context.port_client.get_current_integration()
            raw_config = integration.get("config") or {}

            if is_repo_managed_mapping(integration):
                integration_cfg = self.context.integration_config
                github_org = integration_cfg.get("github_organization")
                if not github_org:
                    logger.error(
                        "mapping is managed by the repository but github_organization is missing "
                        "from the integration configuration."
                    )
                    raise EmptyPortAppConfigError()
                return await load_org_port_app_config(github_org)

            if raw_config:
                logger.debug("Using Port integration config from API")
                return raw_config

            logger.error(
                "Integration Port app config is empty and no repoManagedMapping "
                "flag was specified"
            )
            raise EmptyPortAppConfigError()
