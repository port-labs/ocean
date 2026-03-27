from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.webhook.processor_manager import (
    LiveEventsProcessorManager,
)
from port_ocean.core.integrations.base import BaseIntegration
from bitbucket_cloud.entity_processors.file_entity_processor import FileEntityProcessor
from typing import Any, Literal, Type, Optional
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from pydantic import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.utils.signal import signal_handler
from loguru import logger


FILE_PROPERTY_PREFIX = "file://"

UserRole = Literal["member", "contributor", "admin", "owner"]


class RepositoryBranchMapping(BaseModel):
    name: str = Field(
        default="",
        alias="name",
        description="Specify the repository name",
    )
    branch: str = Field(
        default="default",
        alias="branch",
        description="Specify the branch to bring the folders from",
    )


class RepositorySelector(Selector):
    user_role: Optional[UserRole] = Field(
        default=None,
        alias="userRole",
        title="User Role",
        description="Filter repositories by authenticated user's role: member, contributor, admin, or owner",
    )
    repo_query: Optional[str] = Field(
        default=None,
        alias="repoQuery",
        title="Repository Query",
        description='Query string to narrow repositories as per Bitbucket filtering (e.g., name="my-repo")',
    )
    included_files: list[str] = Field(
        alias="includedFiles",
        default_factory=list,
        title="Included Files",
        description=(
            "List of file paths to fetch from the repository and attach to "
            "the raw data under __includedFiles. E.g. ['README.md', 'CODEOWNERS']"
        ),
    )


class PullRequestSelector(RepositorySelector):
    pull_request_query: str = Field(
        default='state="OPEN"',
        alias="pullRequestQuery",
        title="Pull Request Query",
        description='Query string to narrow pull requests as per Bitbucket filtering (e.g., state="OPEN")',
    )


class FolderPattern(BaseModel):
    path: str = Field(
        default="",
        alias="path",
        description="Specify the repositories and folders to include under this relative path",
        title="Folder sync patterns",
    )
    repos: list[RepositoryBranchMapping] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories and branches to include under this relative path",
        title="Specific Repositories",
    )


class BitbucketFolderSelector(RepositorySelector):
    folders: list[FolderPattern] = Field(
        default_factory=list,
        alias="folders",
        title="Folders",
        description="Specify the repositories, branches and folders to include under this relative path",
    )


class BitbucketFolderResourceConfig(ResourceConfig):
    kind: Literal["folder"] = Field(
        title="Bitbucket Folder",
        description="A folder within a Bitbucket repository, scoped to specific branches and paths",
    )
    selector: BitbucketFolderSelector = Field(
        title="Folder Selector",
        description="Selector to filter and configure which Bitbucket folders are synced",
    )


class BitbucketFilePattern(BaseModel):
    path: str = Field(
        default="*/",
        alias="path",
        description="Specify the path to match files from",
        title="File sync patterns",
    )
    repos: list[str] = Field(
        default_factory=list,
        alias="repos",
        description="Specify the repositories to fetch files from",
        title="Specific Repositories",
    )
    skip_parsing: bool = Field(
        default=False,
        alias="skipParsing",
        description="Skip parsing the files and just return the raw file content",
    )
    filenames: list[str] = Field(
        default_factory=list,
        alias="filenames",
        description="Specify list of filenames to search and return",
    )


class BitbucketFileSelector(Selector):
    files: BitbucketFilePattern
    included_files: list[str] = Field(
        title="Additional files",
        alias="includedFiles",
        default_factory=list,
        description="List of file paths to fetch and attach to the file entity. This selector will add the content of the file to the API response under the `__includedFiles` field.",
    )


class BitbucketFileResourceConfig(ResourceConfig):
    kind: Literal["file"] = Field(
        title="Bitbucket File",
        description="A file within a Bitbucket repository, matched by path and filename patterns",
    )
    selector: BitbucketFileSelector = Field(
        title="File Selector",
        description="Selector to filter and configure which Bitbucket files are synced",
    )


class RepositoryResourceConfig(ResourceConfig):
    kind: Literal["repository"] = Field(
        title="Bitbucket Repository",
        description="A Bitbucket repository synced from your workspace",
    )
    selector: RepositorySelector = Field(
        title="Repository Selector",
        description="Selector to filter and configure which Bitbucket repositories are synced",
    )


class PullRequestResourceConfig(ResourceConfig):
    kind: Literal["pull-request"] = Field(
        title="Bitbucket Pull Request",
        description="A pull request in a Bitbucket repository",
    )
    selector: PullRequestSelector = Field(
        title="Pull Request Selector",
        description="Selector to filter and configure which Bitbucket pull requests are synced",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal["project"] = Field(
        title="Bitbucket Project",
        description="A Bitbucket project that groups repositories within a workspace",
    )


class BitbucketAppConfig(PortAppConfig):
    resources: list[
        BitbucketFolderResourceConfig
        | BitbucketFileResourceConfig
        | PullRequestResourceConfig
        | RepositoryResourceConfig
        | ProjectResourceConfig
    ] = Field(
        default_factory=list,
        alias="resources",
        description="Specify the resources to include in the sync",
    )  # type: ignore[assignment]


class GitManipulationHandler(JQEntityProcessor):
    async def _search(
        self, data: dict[str, Any], pattern: str, field: str | None = None
    ) -> Any:
        entity_processor: Type[JQEntityProcessor]
        if pattern.startswith(FILE_PROPERTY_PREFIX):
            logger.warning(
                f"DEPRECATION: Using 'file://' prefix in mappings is deprecated and will be removed in a future version. "
                f"Pattern: '{pattern}'. "
                f"Use the 'includedFiles' selector instead. Example: "
                f"selector.includedFiles: ['{pattern[len(FILE_PROPERTY_PREFIX) :]}'] "
                f'and mapping: .__includedFiles["{pattern[len(FILE_PROPERTY_PREFIX) :]}"]'
            )
            entity_processor = FileEntityProcessor
        else:
            entity_processor = JQEntityProcessor
        return await entity_processor(self.context)._search(data, pattern, field)


class BitbucketHandlerMixin(HandlerMixin):
    logger.info("Initializing BitbucketHandlerMixin")
    EntityProcessorClass = GitManipulationHandler


class BitbucketLiveEventsProcessorManager(
    LiveEventsProcessorManager, BitbucketHandlerMixin
):
    pass


class BitbucketIntegration(BaseIntegration, BitbucketHandlerMixin):
    def __init__(self, context: PortOceanContext):
        logger.info("Initializing BitbucketIntegration")
        super().__init__(context)
        # Replace the Ocean's webhook manager with our custom one
        self.context.app.webhook_manager = BitbucketLiveEventsProcessorManager(
            self.context.app.integration_router,
            signal_handler,
            self.context.config.max_event_processing_seconds,
            self.context.config.max_wait_seconds_before_shutdown,
        )

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = BitbucketAppConfig
