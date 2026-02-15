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
    repo_search: Optional[RepoSearchParams] = Field(default=None, alias="repoSearch")


class GithubRepositorySelector(RepoSearchSelector):
    include: Optional[List[Literal["collaborators", "teams", "sbom"]]] = Field(
        default_factory=list,
        max_items=3,
        description="Specify the relationships to include in the repository",
    )
    included_files: list[str] = Field(
        alias="includedFiles",
        default_factory=list,
        description=(
            "List of file paths to fetch from the repository and attach to "
            "the raw data under __includedFiles. E.g. ['README.md', 'CODEOWNERS']"
        ),
    )


class GithubRepositoryConfig(ResourceConfig):
    selector: GithubRepositorySelector
    kind: Literal["repository"] = Field(
        title="Repository",
        description="Repository resource",
        const=True,
        extra={"ui_schema": {"hidden": True}},
    )


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        description="Specify the repository name",
    )
    branch: Optional[str] = Field(
        default=None,
        description="Specify the branch to bring the folders from, repo's default branch will be used if none is passed",
    )


class FolderSelector(BaseModel):
    organization: Optional[str] = Field(default=None)
    path: str = Field(default="*")
    repos: Optional[list[RepositoryBranchMapping]] = Field(
        description="Specify the repositories and branches to fetch files from",
        default=None,
    )


class GithubFolderSelector(Selector):
    folders: list[FolderSelector]
    included_files: list[str] = Field(
        alias="includedFiles",
        default_factory=list,
        description="List of file paths to fetch and attach to the folder entity",
    )


class GithubUserSelector(Selector):
    include_bots: bool = Field(
        default=True,
        alias="includeBots",
        description="Include bots in the list of users",
    )


class GithubUserConfig(ResourceConfig):
    selector: GithubUserSelector
    kind: Literal[ObjectKind.USER]


class GithubFolderResourceConfig(ResourceConfig):
    selector: GithubFolderSelector
    kind: Literal[ObjectKind.FOLDER]


class GithubPullRequestSelector(RepoSearchSelector):
    states: list[Literal["open", "closed"]] = Field(
        default=["open"],
        description="Filter by pull request state (e.g., open, closed)",
    )
    max_results: int = Field(
        alias="maxResults",
        default=100,
        ge=1,
        description="Limit the number of pull requests returned",
    )
    since: int = Field(
        default=60,
        ge=1,
        description="Only fetch pull requests updated within the last N days",
    )
    api: Literal["rest", "graphql"] = Field(
        default="rest",
        description="Select the API to use for fetching pull requests",
    )

    @property
    def updated_after(self) -> datetime:
        """Convert the since days to a timezone-aware datetime object."""
        return datetime.now(timezone.utc) - timedelta(days=self.since)


class GithubPullRequestConfig(ResourceConfig):
    selector: GithubPullRequestSelector
    kind: Literal["pull-request"]


class GithubIssueSelector(RepoSearchSelector):
    state: Literal["open", "closed", "all"] = Field(
        default="open",
        description="Filter by issue state (open, closed, all)",
    )
    labels: Optional[list[str]] = Field(
        default=None,
        description="Filter issues by labels. Issues must have ALL of the specified labels. Example: ['bug', 'enhancement']",
    )

    @property
    def labels_str(self) -> Optional[str]:
        """Convert labels list to comma-separated string for GitHub API."""
        return ",".join(self.labels) if self.labels else None


class GithubIssueConfig(ResourceConfig):
    selector: GithubIssueSelector
    kind: Literal["issue"]


class GithubTeamSector(Selector):
    members: bool = Field(default=True)


class GithubTeamConfig(ResourceConfig):
    selector: GithubTeamSector
    kind: Literal[ObjectKind.TEAM]


class GithubDependabotAlertSelector(RepoSearchSelector):
    states: list[Literal["auto_dismissed", "dismissed", "fixed", "open"]] = Field(
        default=["open"],
        description="Filter alerts by state (auto_dismissed, dismissed, fixed, open)",
    )
    severity: Optional[list[Literal["low", "medium", "high", "critical"]]] = Field(
        default=None,
        description="Filter alerts by severities. A comma-separated list of severities. If specified, only alerts with these severities will be returned. Example: ['low', 'medium']",
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
        default=None,
        description="Filter alerts by ecosystems. Only alerts for these ecosystems will be returned. Example: ['npm', 'pip']",
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
    selector: GithubDependabotAlertSelector
    kind: Literal["dependabot-alert"]


class GithubCodeScanningAlertSelector(RepoSearchSelector):
    state: Literal["open", "closed", "dismissed", "fixed"] = Field(
        default="open",
        description="Filter alerts by state (open, closed, dismissed, fixed)",
    )
    severity: Optional[
        Literal["critical", "high", "medium", "low", "warning", "note", "error"]
    ] = Field(
        default=None,
        description="Filter alerts by severity level. If specified, only code scanning alerts with this severity will be returned.",
    )


class GithubCodeScanningAlertConfig(ResourceConfig):
    selector: GithubCodeScanningAlertSelector
    kind: Literal["code-scanning-alerts"]


class GithubDeploymentSelector(RepoSearchSelector):
    task: Optional[str] = Field(
        default=None,
        description="Filter deployments by task name (e.g., deploy or deploy:migrations)",
    )
    environment: Optional[str] = Field(
        default=None,
        description="Filter deployments by environment name (e.g., staging or production)",
    )


class GithubDeploymentConfig(ResourceConfig):
    selector: GithubDeploymentSelector
    kind: Literal["deployment"]


class GithubSecretScanningAlertSelector(RepoSearchSelector):
    state: Literal["open", "resolved", "all"] = Field(
        default="open",
        description="Filter alerts by state (open, resolved, all)",
    )
    hide_secret: bool = Field(
        alias="hideSecret",
        default=True,
        description="Whether to hide the actual secret content in the alert data for security purposes",
    )


class GithubSecretScanningAlertConfig(ResourceConfig):
    selector: GithubSecretScanningAlertSelector
    kind: Literal["secret-scanning-alerts"]


class GithubFilePattern(BaseModel):
    organization: Optional[str] = Field(default=None)
    path: str = Field(
        alias="path",
        description="Specify the path to match files from",
    )
    repos: Optional[list[RepositoryBranchMapping]] = Field(
        alias="repos",
        description="Specify the repositories and branches to fetch files from",
        default=None,
    )
    skip_parsing: bool = Field(
        default=False,
        alias="skipParsing",
        description="Skip parsing the files and just return the raw file content",
    )
    validation_check: bool = Field(
        default=False,
        alias="validationCheck",
        description="Enable validation for this file pattern during pull request processing",
    )


class GithubFileSelector(Selector):
    files: list[GithubFilePattern]
    included_files: list[str] = Field(
        alias="includedFiles",
        default_factory=list,
        description="List of file paths to fetch and attach to the file entity",
    )


class GithubFileResourceConfig(ResourceConfig):
    kind: Literal["file"]
    selector: GithubFileSelector


class GithubBranchSelector(RepoSearchSelector):
    detailed: bool = Field(
        default=False, description="Include extra details about the branch"
    )
    default_branch_only: bool = Field(
        default=False,
        alias="defaultBranchOnly",
        description=(
            "If true, only the repository's default branch will be synced. "
            "If provided, it takes precedence and branchNames will be ignored."
        ),
    )
    protection_rules: bool = Field(
        default=False,
        alias="protectionRules",
        description="Include protection rules for the branch",
    )
    branch_names: List[str] = Field(
        default_factory=list,
        alias="branchNames",
        description="List of branch names to fetch. If provided, the branch names will be fetched explicitly and not using pagination.",
    )


class GithubBranchConfig(ResourceConfig):
    kind: Literal["branch"]
    selector: GithubBranchSelector


class GithubRepoSearchConfig(ResourceConfig):
    selector: RepoSearchSelector


class GithubPortAppConfig(PortAppConfig):
    organizations: List[str] = Field(
        default_factory=list,
        description=(
            "List of GitHub organization names (optional - if not provided, "
            "will sync all organizations the personal access token user is a "
            "member of) for Classic PAT authentication."
        ),
    )
    include_authenticated_user: bool = Field(
        default=False,
        alias="includeAuthenticatedUser",
        description="Include the authenticated user's personal account",
    )
    repository_type: str = Field(alias="repositoryType", default="all")
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
        | GithubRepoSearchConfig
        | ResourceConfig
    ] = Field(default_factory=list)


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

    allow_custom_kinds = True

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
