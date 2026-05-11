from typing import Any, cast

from azure_devops.helpers import resync
from azure_devops.misc import (
    Kind,
    AzureDevopsFolderResourceConfig,
)
from azure_devops.webhooks.setup import setup_webhooks_for_all_orgs
from azure_devops.webhooks.webhook_processors.branch_webhook_processor import (
    BranchWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.folder_webhook_processor import (
    FolderWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.gitops_webhook_processor import (
    GitopsWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.pull_request_processor import (
    PullRequestWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.repository_processor import (
    RepositoryWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.work_item_webhook_processor import (
    WorkItemWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.advanced_security_webhook_processor import (
    AdvancedSecurityWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.pipeline_webhook_processor import (
    PipelineWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.pipeline_stage_webhook_processor import (
    PipelineStageWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.pipeline_run_webhook_processor import (
    PipelineRunWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.release_webhook_processor import (
    ReleaseWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.release_definition_webhook_processor import (
    ReleaseDefinitionWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.test_run_webhook_processor import (
    TestRunWebhookProcessor,
)
from azure_devops.webhooks.webhook_processors.release_deployment_webhook_processor import (
    ReleaseDeploymentWebhookProcessor,
)
from integration import (
    AzureDevopsPipelineResourceConfig,
    AzureDevopsProjectResourceConfig,
    AzureDevopsFileResourceConfig,
    AzureDevopsReleaseConfig,
    AzureDevopsReleaseDefinitionConfig,
    AzureDevopsTeamResourceConfig,
    AzureDevopsWorkItemResourceConfig,
    AzureDevopsTestRunResourceConfig,
    AzureDevopsPullRequestResourceConfig,
    AzureDevopsAdvancedSecurityResourceConfig,
    AzureDevopsRepositoryResourceConfig,
    AzureDevopsUserConfig,
)
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


@ocean.on_resync(Kind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsProjectResourceConfig, event.resource_config).selector
    async for batch in resync.iter_projects(selector.default_team):
        yield batch


@ocean.on_resync(Kind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_users():
        yield batch


@ocean.on_resync(Kind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsTeamResourceConfig, event.resource_config).selector
    async for batch in resync.iter_teams(selector.include_members):
        yield batch


@ocean.on_resync(Kind.MEMBER)
async def resync_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_members():
        yield batch


@ocean.on_resync(Kind.GROUP)
async def resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_groups():
        yield batch


@ocean.on_resync(Kind.GROUP_MEMBER)
async def resync_group_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_group_members():
        yield batch


@ocean.on_resync(Kind.PIPELINE)
async def resync_pipeline(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsPipelineResourceConfig, event.resource_config)
    async for batch in resync.iter_pipelines(config.selector.include_repo):
        yield batch


@ocean.on_resync(Kind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(
        AzureDevopsPullRequestResourceConfig, event.resource_config
    ).selector
    async for batch in resync.iter_pull_requests(
        selector.min_time_datetime, selector.max_results
    ):
        yield batch


@ocean.on_resync(Kind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsRepositoryResourceConfig, event.resource_config).selector
    async for batch in resync.iter_repositories(selector.included_files or []):
        yield batch


@ocean.on_resync(Kind.BRANCH)
async def resync_branches(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_branches():
        yield batch


@ocean.on_resync(Kind.REPOSITORY_POLICY)
async def resync_repository_policies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_repository_policies():
        yield batch


@ocean.on_resync(Kind.WORK_ITEM)
async def resync_workitems(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsWorkItemResourceConfig, event.resource_config)
    async for batch in resync.iter_work_items(
        wiql=config.selector.wiql, expand=config.selector.expand
    ):
        yield batch


@ocean.on_resync(Kind.COLUMN)
async def resync_columns(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_columns():
        yield batch


@ocean.on_resync(Kind.BOARD)
async def resync_boards(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_boards():
        yield batch


@ocean.on_resync(Kind.RELEASE)
async def resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsReleaseConfig, event.resource_config)
    async for batch in resync.iter_releases(
        additional_params=config.selector.to_params(),
    ):
        yield batch


@ocean.on_resync(Kind.RELEASE_DEFINITION)
async def resync_release_definitions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsReleaseDefinitionConfig, event.resource_config)
    async for batch in resync.iter_release_definitions(
        additional_params=config.selector.to_params(),
    ):
        yield batch


@ocean.on_resync(Kind.BUILD)
async def resync_builds(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_builds():
        yield batch


@ocean.on_resync(Kind.PIPELINE_STAGE)
async def resync_pipeline_stages(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_pipeline_stages():
        yield batch


@ocean.on_resync(Kind.ENVIRONMENT)
async def resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_environments():
        yield batch


@ocean.on_resync(Kind.RELEASE_DEPLOYMENT)
async def resync_release_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_release_deployments():
        yield batch


@ocean.on_resync(Kind.PIPELINE_DEPLOYMENT)
async def resync_pipeline_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_pipeline_deployments():
        yield batch


@ocean.on_resync(Kind.FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    config = cast(AzureDevopsFileResourceConfig, event.resource_config)
    async for batch in resync.iter_files(
        paths=config.selector.files.path,
        repos=config.selector.files.repos,
        included_files=config.selector.included_files or [],
    ):
        yield batch


@ocean.on_resync(Kind.PIPELINE_RUN)
async def resync_pipeline_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_pipeline_runs():
        yield batch


@ocean.on_resync(Kind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync folders based on configuration."""
    selector = cast(AzureDevopsFolderResourceConfig, event.resource_config).selector
    async for batch in resync.iter_folders(
        folders=selector.folders,
        project_name=selector.project_name,
        included_files=selector.included_files or [],
    ):
        yield batch


@ocean.on_resync(Kind.TEST_RUN)
async def resync_test_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AzureDevopsTestRunResourceConfig, event.resource_config).selector
    async for batch in resync.iter_test_runs(
        include_results=selector.include_results,
        coverage_config=selector.code_coverage,
    ):
        yield batch


@ocean.on_resync(Kind.ITERATION)
async def resync_iterations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync.iter_iterations():
        yield batch


@ocean.on_resync(Kind.ADVANCED_SECURITY_ALERT)
async def resync_advanced_security_alerts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(
        AzureDevopsAdvancedSecurityResourceConfig, event.resource_config
    ).selector
    params: dict[str, Any] = {}
    if selector.criteria:
        params = selector.criteria.as_params

    async for batch in resync.iter_advanced_security_alerts(params):
        yield batch


@ocean.on_start()
async def setup_webhooks() -> None:
    await setup_webhooks_for_all_orgs()


ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", FileWebhookProcessor)
ocean.add_webhook_processor("/webhook", GitopsWebhookProcessor)
ocean.add_webhook_processor("/webhook", FolderWebhookProcessor)
ocean.add_webhook_processor("/webhook", BranchWebhookProcessor)
ocean.add_webhook_processor("/webhook", WorkItemWebhookProcessor)
ocean.add_webhook_processor("/webhook", AdvancedSecurityWebhookProcessor)
ocean.add_webhook_processor("/webhook", PipelineWebhookProcessor)
ocean.add_webhook_processor("/webhook", PipelineStageWebhookProcessor)
ocean.add_webhook_processor("/webhook", PipelineRunWebhookProcessor)
ocean.add_webhook_processor("/webhook", ReleaseWebhookProcessor)
ocean.add_webhook_processor("/webhook", ReleaseDefinitionWebhookProcessor)
ocean.add_webhook_processor("/webhook", ReleaseDeploymentWebhookProcessor)
ocean.add_webhook_processor("/webhook", TestRunWebhookProcessor)
