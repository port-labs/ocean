from typing import Any

from loguru import logger

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.enrichments.included_files import (
    FileIncludedFilesStrategy,
    FolderIncludedFilesStrategy,
    IncludedFilesEnricher,
    RepositoryIncludedFilesStrategy,
)
from azure_devops.helpers.multi_org import iterate_per_organization
from azure_devops.misc import (
    ACTIVE_PULL_REQUEST_SEARCH_CRITERIA,
    FolderPattern,
    create_closed_pull_request_search_criteria,
)


async def _enrich_repos_batch_with_included_files(
    client: AzureDevopsClient,
    repositories: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of repositories with the content of ``file_paths``."""
    if not file_paths or not repositories:
        return repositories
    enricher = IncludedFilesEnricher(
        client=client,
        strategy=RepositoryIncludedFilesStrategy(included_files=file_paths),
    )
    return await enricher.enrich_batch(repositories)


async def iter_projects(sync_default_team: bool) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for projects in client.generate_projects(sync_default_team):
            logger.info(f"Resyncing {len(projects)} projects")
            yield projects

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_users(
    additional_params: dict[str, str] | None = None
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for users in client.generate_users(additional_params):
            logger.info(f"Resyncing {len(users)} users")
            yield users

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_teams(include_members: bool) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for teams in client.generate_teams():
            logger.info(f"Resyncing {len(teams)} teams")
            if include_members:
                logger.info(f"Enriching {len(teams)} teams with members")
                yield await client.enrich_teams_with_members(teams)
            else:
                yield teams

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_members() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for members in client.generate_members():
            logger.info(f"Resyncing {len(members)} members")
            yield members

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_groups() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for groups in client.generate_groups():
            logger.info(f"Resyncing {len(groups)} groups")
            yield groups

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_group_members() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for members in client.generate_group_members():
            logger.info(f"Resyncing {len(members)} group members")
            yield members

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_pipelines(include_repo: bool) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for pipelines in client.generate_pipelines():
            logger.info(f"Resyncing {len(pipelines)} pipelines")
            if include_repo:
                logger.info(f"Enriching {len(pipelines)} pipelines with repository")
                pipelines = await client.enrich_pipelines_with_repository(pipelines)
            yield pipelines

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_pull_requests(
    min_time_datetime: Any,
    max_results: int,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for pull_requests in client.generate_pull_requests(
            ACTIVE_PULL_REQUEST_SEARCH_CRITERIA
        ):
            logger.info(f"Resyncing {len(pull_requests)} active pull_requests")
            yield pull_requests

        for search_filter in create_closed_pull_request_search_criteria(
            min_time_datetime
        ):
            async for pull_requests in client.generate_pull_requests(
                search_filter, max_results
            ):
                logger.info(
                    f"Resyncing {len(pull_requests)} abandoned/completed pull_requests"
                )
                yield pull_requests

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_repositories(
    included_files: list[str],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for repositories in client.generate_repositories():
            logger.info(f"Resyncing {len(repositories)} repositories")
            if included_files:
                repositories = await _enrich_repos_batch_with_included_files(
                    client, repositories, included_files
                )
            yield repositories

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_branches() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for branches in client.generate_branches():
            logger.info(f"Resyncing {len(branches)} branches")
            yield branches

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_repository_policies() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for policies in client.generate_repository_policies():
            logger.info(f"Resyncing {len(policies)} repository policies")
            yield policies

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_work_items(
    wiql: str | None,
    expand: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for work_items in client.generate_work_items(wiql=wiql, expand=expand):
            logger.info(f"Resyncing {len(work_items)} work items")
            yield work_items

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_columns() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for columns in client.get_columns():
            logger.info(f"Resyncing {len(columns)} columns")
            yield columns

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_boards() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for boards in client.get_boards_in_organization():
            logger.info(f"Resyncing {len(boards)} boards")
            yield boards

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_releases(
    additional_params: dict[str, str] | None = None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for releases in client.generate_releases(
            additional_params=additional_params,
        ):
            logger.info(f"Resyncing {len(releases)} releases")
            yield releases

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_release_definitions(
    additional_params: dict[str, str] | None = None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for definitions in client.generate_release_definitions(
            additional_params=additional_params,
        ):
            logger.info(f"Resyncing {len(definitions)} release definitions")
            yield definitions

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_builds() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for builds in client.generate_builds():
            logger.info(f"Resyncing {len(builds)} builds")
            yield builds

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_pipeline_stages() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for stages in client.generate_pipeline_stages():
            logger.info(f"Resyncing {len(stages)} pipeline stages")
            yield stages

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_environments() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for environments in client.generate_environments():
            logger.info(f"Fetched {len(environments)} environments")
            yield environments

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_release_deployments() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for deployments in client.generate_release_deployments():
            logger.info(f"Fetched {len(deployments)} release deployments")
            yield deployments

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_pipeline_deployments() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for environments in client.generate_environments():
            tasks = [
                client.generate_pipeline_deployments(
                    environment_id=environment["id"],
                    project=environment["project"],
                )
                for environment in environments
            ]
            async for deployments in stream_async_iterators_tasks(*tasks):
                logger.info(f"Fetched {len(deployments)} pipeline deployments")
                yield deployments

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_files(
    paths: str | list[str],
    repos: list[str] | None,
    included_files: list[str],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Starting file resync for paths: {paths}")

    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for files_batch in client.generate_files(path=paths, repos=repos):
            if files_batch:
                logger.info(f"Resyncing batch of {len(files_batch)} files")
                if included_files:
                    enricher = IncludedFilesEnricher(
                        client=client,
                        strategy=FileIncludedFilesStrategy(
                            included_files=included_files
                        ),
                    )
                    files_batch = await enricher.enrich_batch(files_batch)
                yield files_batch

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_pipeline_runs() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for runs in client.generate_pipeline_runs():
            logger.info(f"Resyncing {len(runs)} pipeline runs")
            yield runs

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_folders(
    folders: list[FolderPattern],
    project_name: str | None,
    included_files: list[str],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for matching_folders in client.process_folder_patterns(
            folders, project_name
        ):
            if included_files:
                enricher = IncludedFilesEnricher(
                    client=client,
                    strategy=FolderIncludedFilesStrategy(
                        folder_selectors=folders,
                        global_included_files=included_files,
                    ),
                )
                matching_folders = await enricher.enrich_batch(matching_folders)
            yield matching_folders

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_test_runs(
    include_results: bool,
    coverage_config: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for test_runs in client.fetch_test_runs(include_results, coverage_config):
            logger.info(f"Fetched {len(test_runs)} test runs")
            yield test_runs

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_iterations() -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for iterations in client.generate_iterations():
            logger.info(f"Resyncing {len(iterations)} iterations")
            yield iterations

    async for batch in iterate_per_organization(_handler):
        yield batch


async def iter_advanced_security_alerts(
    params: dict[str, Any],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async def _handler(client: AzureDevopsClient) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for repositories in client.generate_repositories():
            for repository in repositories:
                async for security_alerts in client.generate_advanced_security_alerts(
                    repository, params
                ):
                    logger.info(f"Resyncing {len(security_alerts)} security alerts")
                    yield security_alerts

    async for batch in iterate_per_organization(_handler):
        yield batch
