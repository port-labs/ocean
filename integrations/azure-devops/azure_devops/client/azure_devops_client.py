from azure_devops.webhooks.events import AdvancedSecurityAlertEvents
import asyncio
import functools
import json
import httpx
from collections import defaultdict
from itertools import batched
from typing import Any, AsyncGenerator, Awaitable, Optional, Callable, Iterable
from httpx import HTTPStatusError, ReadTimeout
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.utils.cache import cache_iterator_result

from azure_devops.webhooks.webhook_event import WebhookSubscription
from azure_devops.webhooks.events import (
    BuildEvents,
    RepositoryEvents,
    PullRequestEvents,
    PushEvents,
    WorkItemEvents,
    PipelineEvents,
    PipelineStageEvents,
    PipelineRunEvents,
    ReleaseEvents,
    ReleaseDeploymentEvents,
)

from azure_devops.client.auth import AuthProvider, build_auth_provider
from azure_devops.client.base_client import MAX_TIMEMOUT_RETRIES, HTTPBaseClient
from azure_devops.misc import FolderPattern, RepositoryBranchMapping
from azure_devops.client.base_client import PAGE_SIZE

from azure_devops.client.file_processing import (
    PathDescriptor,
    RecursionLevel,
    extract_descriptor_from_pattern,
    get_priority,
    group_descriptors_by_base,
    filter_files_by_glob,
    parse_file_content,
    separate_glob_and_literal_paths,
)
from port_ocean.utils.async_iterators import (
    stream_async_iterators_tasks,
    semaphore_async_iterator,
)
from port_ocean.utils.queue_utils import process_in_queue
from urllib.parse import urlparse
from typing import TYPE_CHECKING
import fnmatch

if TYPE_CHECKING:
    from integration import CodeCoverageConfig

API_URL_PREFIX = "_apis"
PROJECT_TAG_PROPERTY_PREFIX = "Microsoft.TeamFoundation.Project.Tag."
WEBHOOK_API_PARAMS = {"api-version": "7.1-preview.1"}
ADVANCED_SECURITY_API_PARAMS = {"api-version": "7.2-preview.1"}
ADVANCED_SECURITY_PUBLISHER_ID = "advsec"
PIPELINES_PUBLISHER_ID = "pipelines"
RELEASE_PUBLISHER_ID = "rm"
API_PARAMS = {"api-version": "7.1"}
WEBHOOK_URL_SUFFIX = "/integration/webhook"
# Maximum number of work item IDs allowed in a single API request
# (based on Azure DevOps API limitations) https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/list?view=azure-devops-rest-7.1&tabs=HTTP
MAX_WORK_ITEMS_PER_REQUEST = 200
MAX_WORK_ITEMS_RESULTS_PER_PROJECT = 19999
MAX_ALLOWED_FILE_SIZE_IN_BYTES = 1 * 1024 * 1024
MAX_CONCURRENT_FILE_DOWNLOADS = 50
MAX_CONCURRENT_REPOS_FOR_FILE_PROCESSING = 25
MAX_CONCURRENT_REPOS_FOR_PULL_REQUESTS = 25
MAX_SUBJECTS_PER_LOOKUP = 500
# Conservative concurrency caps to avoid exhausting the shared ADO TSTU budget.
# ADO does not publish a per-connection limit; these values are empirically chosen
# to keep concurrent fanout low enough that the TSTU window resets before exhaustion.
MAX_CONCURRENT_PROJECTS = 5
MAX_CONCURRENT_TEAMS = 5
MAX_CONCURRENT_PIPELINES = 5
MAX_CONCURRENT_SUBSCRIPTION_REQUESTS = 5

# Webhook subscriptions for Azure DevOps events
AZURE_DEVOPS_WEBHOOK_SUBSCRIPTIONS = [
    WebhookSubscription(
        publisherId="tfs", eventType=PullRequestEvents.PULL_REQUEST_CREATED
    ),
    WebhookSubscription(
        publisherId="tfs", eventType=PullRequestEvents.PULL_REQUEST_UPDATED
    ),
    WebhookSubscription(publisherId="tfs", eventType=PushEvents.PUSH),
    WebhookSubscription(publisherId="tfs", eventType=RepositoryEvents.REPO_CREATED),
    WebhookSubscription(publisherId="tfs", eventType=WorkItemEvents.WORK_ITEM_CREATED),
    WebhookSubscription(publisherId="tfs", eventType=WorkItemEvents.WORK_ITEM_UPDATED),
    WebhookSubscription(
        publisherId="tfs", eventType=WorkItemEvents.WORK_ITEM_COMMENTED
    ),
    WebhookSubscription(publisherId="tfs", eventType=WorkItemEvents.WORK_ITEM_DELETED),
    WebhookSubscription(publisherId="tfs", eventType=BuildEvents.BUILD_COMPLETE),
    WebhookSubscription(publisherId="tfs", eventType=WorkItemEvents.WORK_ITEM_RESTORED),
    WebhookSubscription(
        publisherId=ADVANCED_SECURITY_PUBLISHER_ID,
        eventType=AdvancedSecurityAlertEvents.SECURITY_ALERT_CREATED,
    ),
    WebhookSubscription(
        publisherId=ADVANCED_SECURITY_PUBLISHER_ID,
        eventType=AdvancedSecurityAlertEvents.SECURITY_ALERT_STATE_CHANGED,
    ),
    WebhookSubscription(
        publisherId=ADVANCED_SECURITY_PUBLISHER_ID,
        eventType=AdvancedSecurityAlertEvents.SECURITY_ALERT_UPDATED,
    ),
    WebhookSubscription(
        publisherId=PIPELINES_PUBLISHER_ID,
        eventType=PipelineEvents.PIPELINE_UPDATED,
    ),
    WebhookSubscription(
        publisherId=PIPELINES_PUBLISHER_ID,
        eventType=PipelineStageEvents.PIPELINE_JOB_STATE_CHANGED,
    ),
    WebhookSubscription(
        publisherId=PIPELINES_PUBLISHER_ID,
        eventType=PipelineStageEvents.PIPELINE_STAGE_STATE_CHANGED,
    ),
    WebhookSubscription(
        publisherId=PIPELINES_PUBLISHER_ID,
        eventType=PipelineStageEvents.PIPELINE_STAGE_APPROVAL_PENDING,
    ),
    WebhookSubscription(
        publisherId=PIPELINES_PUBLISHER_ID,
        eventType=PipelineStageEvents.PIPELINE_STAGE_APPROVAL_COMPLETED,
    ),
    WebhookSubscription(
        publisherId=PIPELINES_PUBLISHER_ID,
        eventType=PipelineRunEvents.PIPELINE_RUN_STATE_CHANGED,
    ),
    WebhookSubscription(
        publisherId=RELEASE_PUBLISHER_ID,
        eventType=ReleaseEvents.RELEASE_CREATED,
    ),
    WebhookSubscription(
        publisherId=RELEASE_PUBLISHER_ID,
        eventType=ReleaseEvents.RELEASE_ABANDONED,
    ),
    WebhookSubscription(
        publisherId=RELEASE_PUBLISHER_ID,
        eventType=ReleaseDeploymentEvents.DEPLOYMENT_STARTED,
    ),
    WebhookSubscription(
        publisherId=RELEASE_PUBLISHER_ID,
        eventType=ReleaseDeploymentEvents.DEPLOYMENT_COMPLETED,
    ),
]


def _normalize_area_path(path: str) -> str:
    """Convert a classification-node path to work-item ``System.AreaPath`` format.

    Example: ``\\Project\\Area\\L1\\L2`` → ``Project\\L1\\L2``.
    """
    segments = path.strip("\\").split("\\")
    # segments[0] is the project name; segments[1] is the "Area" structure group.
    if len(segments) >= 2 and segments[1] == "Area":
        del segments[1]
    return "\\".join(segments)


def _flatten_area_path_tree(
    node: dict[str, Any],
    project: dict[str, Any],
    parent_identifier: Optional[str],
) -> list[dict[str, Any]]:
    """Flatten a nested area tree into one dict per node, with project and parent context."""
    if node.get("structureType") != "area":
        return []

    enriched = {
        **{key: value for key, value in node.items() if key != "children"},
        "__project": project,
        "__parentIdentifier": parent_identifier,
        "__normalizedPath": _normalize_area_path(node.get("path", "")),
    }
    result = [enriched]
    for child in node.get("children", []):
        result.extend(_flatten_area_path_tree(child, project, node.get("identifier")))
    return result


class AzureDevopsClient(HTTPBaseClient):
    def __init__(
        self,
        organization_url: str,
        auth_provider: AuthProvider,
        webhook_auth_username: Optional[str] = None,
        excluded_tags: Optional[list[str]] = None,
    ) -> None:
        super().__init__(auth_provider)
        self._organization_base_url = organization_url
        self._advsec_base_url = f"{organization_url.replace('dev.', f'{ADVANCED_SECURITY_PUBLISHER_ID}.dev.')}"
        self.webhook_auth_username = webhook_auth_username
        self.excluded_tags = excluded_tags

    @classmethod
    def create_from_ocean_config(cls) -> "AzureDevopsClient":
        if cache := event.attributes.get("azure_devops_client"):
            return cache
        auth_provider = build_auth_provider(ocean.integration_config)
        azure_devops_client = cls(
            ocean.integration_config["organization_url"].strip("/"),
            auth_provider,
            ocean.integration_config.get("webhook_auth_username"),
            ocean.integration_config.get("excluded_tags"),
        )
        event.attributes["azure_devops_client"] = azure_devops_client
        return azure_devops_client

    @classmethod
    def create_from_ocean_config_no_cache(cls) -> "AzureDevopsClient":
        auth_provider = build_auth_provider(ocean.integration_config)
        azure_devops_client = cls(
            ocean.integration_config["organization_url"].strip("/"),
            auth_provider,
            ocean.integration_config.get("webhook_auth_username"),
            ocean.integration_config.get("excluded_tags"),
        )
        return azure_devops_client

    @classmethod
    def _repository_is_healthy(cls, repository: dict[str, Any]) -> bool:
        UNHEALTHY_PROJECT_STATES = {
            "deleted",
            "deleting",
            "new",
            "createPending",
        }
        return repository.get("project", {}).get(
            "state"
        ) not in UNHEALTHY_PROJECT_STATES and not repository.get("isDisabled")

    async def get_single_project(self, project_id: str) -> dict[str, Any] | None:
        project_url = (
            f"{self._organization_base_url}/{API_URL_PREFIX}/projects/{project_id}"
        )
        response = await self.send_request("GET", project_url)
        if not response:
            return None
        project = response.json()
        return project

    async def get_project_tags(self, project_id: str) -> list[dict[str, Any]]:
        url = f"{self._organization_base_url}/{API_URL_PREFIX}/projects/{project_id}/properties"
        response = await self.send_request(
            "GET",
            url,
            params={
                "keys": f"{PROJECT_TAG_PROPERTY_PREFIX}*",
                "api-version": "7.1-preview.1",
            },
        )
        if not response:
            return []
        return response.json().get("value", [])

    async def filter_projects_by_excluded_tags(
        self,
        projects: list[dict[str, Any]],
        exclude_tags: list[str],
    ) -> list[dict[str, Any]]:
        exclude_set = set(exclude_tags)
        semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_PROJECTS)

        async def get_tags_with_semaphore(project_id: str) -> list[dict[str, Any]]:
            async with semaphore:
                return await self.get_project_tags(project_id)

        tags_results = await asyncio.gather(
            *[get_tags_with_semaphore(project["id"]) for project in projects],
            return_exceptions=True,
        )
        filtered = []
        for project, tags in zip(projects, tags_results):
            if isinstance(tags, BaseException):
                logger.warning(
                    "Failed to fetch tags for project %s, including in sync: %s",
                    project["id"],
                    tags,
                )
                filtered.append(project)
            elif exclude_set.isdisjoint(
                t["name"].removeprefix(PROJECT_TAG_PROPERTY_PREFIX) for t in tags
            ):
                filtered.append(project)
        return filtered

    async def generate_projects(
        self, sync_default_team: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        exclude_tags = tuple(self.excluded_tags) if self.excluded_tags else ()
        async for batch in self._generate_projects_cached(
            self._organization_base_url, sync_default_team, exclude_tags
        ):
            yield batch

    @cache_iterator_result()
    async def _generate_projects_cached(
        self,
        org_identifier: str,
        sync_default_team: bool = False,
        exclude_tags: tuple[str, ...] = (),
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        sync_default_team: bool - The List projects endpoint of ADO API excludes default team of a project.
        By setting leveraging the sync_default_team flag, we optionally fetch the default team from the get project
        endpoint using the project id which we obtain from the list projects endpoint.
        read more -> https://learn.microsoft.com/en-us/rest/api/azure/devops/core/projects/list?view=azure-devops-rest-7.1&tabs=HTTP#teamprojectreference
        """

        params = {"includeCapabilities": "true"}
        projects_url = f"{self._organization_base_url}/{API_URL_PREFIX}/projects"
        async for projects in self._get_paginated_by_top_and_continuation_token(
            projects_url, additional_params=params
        ):
            if sync_default_team:
                logger.info("Adding default team to projects")
                semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_PROJECTS)

                async def get_project_with_semaphore(
                    project_id: str,
                ) -> dict[str, Any] | None:
                    async with semaphore:
                        return await self.get_single_project(project_id)

                tasks = [
                    get_project_with_semaphore(project["id"]) for project in projects
                ]
                projects_batch: list[dict[str, Any] | None] = await asyncio.gather(
                    *tasks
                )
                projects = [project for project in projects_batch if project]
            if exclude_tags:
                projects = await self.filter_projects_by_excluded_tags(
                    projects, list(exclude_tags)
                )
            if projects:
                yield projects

    async def get_single_advanced_security_alert(
        self,
        project_id: str,
        repository_id: str,
        alert_id: str,
    ) -> dict[str, Any] | None:
        security_alert_url = f"{self._advsec_base_url}/{project_id}/{API_URL_PREFIX}/alert/repositories/{repository_id}/alerts/{alert_id}"
        response = await self.send_request("GET", security_alert_url)
        if not response:
            return None
        security_alert = response.json()
        return security_alert

    async def generate_advanced_security_alerts(
        self,
        repository: dict[str, Any],
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Generate security alerts from GitHub Advanced Security (GHAS) in Azure DevOps.
        This method fetches alerts for all repositories across all projects using the Advanced Security API.
        read more -> https://learn.microsoft.com/en-us/rest/api/azure/devops/advancedsecurity/alerts/list?view=azure-devops-rest-7.2
        """
        try:
            project_id = repository["project"]["id"]
            repository_id = repository["id"]
            security_alerts_url = f"{self._advsec_base_url}/{project_id}/{API_URL_PREFIX}/alert/repositories/{repository_id}/alerts"
            additional_params = {
                **ADVANCED_SECURITY_API_PARAMS,
            }

            if params:
                additional_params.update(params)
            async for (
                security_alerts
            ) in self._get_paginated_by_top_and_continuation_token(
                security_alerts_url, additional_params=additional_params
            ):
                enriched_alerts = [
                    self._enrich_security_alert(
                        security_alert, repository_id, project_id
                    )
                    for security_alert in security_alerts
                ]
                yield enriched_alerts
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.error(
                    f"Advanced Security not enabled for repository {repository['name']} in project {project_id}"
                )
            raise

    def _enrich_security_alert(
        self, security_alert: dict[str, Any], repository_id: str, project_id: str
    ) -> dict[str, Any]:
        return {
            **security_alert,
            "__repositoryId": repository_id,
            "__projectId": project_id,
        }

    async def generate_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._generate_teams_cached(self._organization_base_url):
            yield batch

    @cache_iterator_result()
    async def _generate_teams_cached(
        self, org_identifier: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        teams_url = f"{self._organization_base_url}/{API_URL_PREFIX}/teams"
        async for teams in self._get_paginated_by_top_and_skip(teams_url):
            yield teams

    async def get_team_members(self, team: dict[str, Any]) -> list[dict[str, Any]]:
        members_url = (
            f"{self._organization_base_url}/{API_URL_PREFIX}/projects/"
            f"{team['projectId']}/teams/{team['id']}/members"
        )
        members = []
        async for members_batch in self._get_paginated_by_top_and_skip(
            members_url,
        ):
            members.extend(members_batch)
        return members

    async def enrich_teams_with_members(
        self, teams: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        logger.debug(f"Fetching members for {len(teams)} teams")
        semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_TEAMS)

        async def get_members_with_semaphore(
            team: dict[str, Any],
        ) -> list[dict[str, Any]]:
            async with semaphore:
                return await self.get_team_members(team)

        team_tasks = [get_members_with_semaphore(team) for team in teams]

        members_results = await asyncio.gather(*team_tasks)

        total_members = sum(len(members) for members in members_results)
        logger.info(f"Retrieved {total_members} members across {len(teams)} teams")

        for team, members in zip(teams, members_results):
            team["__members"] = members

        return teams

    async def get_team_field_values(
        self, team: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Get a team's configured area paths (Team Field Values)."""
        field_values_url = (
            f"{self._organization_base_url}/{team['projectId']}/{team['id']}"
            f"/{API_URL_PREFIX}/work/teamsettings/teamfieldvalues"
        )
        response = await self.send_request("GET", field_values_url, params=API_PARAMS)
        return response.json() if response else None

    async def enrich_teams_with_area_paths(
        self, teams: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        logger.debug(f"Fetching area paths for {len(teams)} teams")

        team_tasks = [self.get_team_field_values(team) for team in teams]

        field_values_results = await asyncio.gather(*team_tasks, return_exceptions=True)

        for team, result in zip(teams, field_values_results):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, BaseException):
                logger.warning(
                    f"Failed to fetch area paths for team {team['id']} in project {team['projectId']}: {result}"
                )
                team["__areaPaths"] = None
            else:
                team["__areaPaths"] = result

        return teams

    async def generate_members(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for teams in self.generate_teams():
            for team in teams:
                members = await self.get_team_members(team)
                for member in members:
                    member["__teamId"] = team["id"]
                yield members

    def _is_azure_devops_services(self) -> bool:
        """Check if the base URL is Azure DevOps Services."""
        hostname = urlparse(self._organization_base_url).hostname or ""
        return hostname.lower().endswith((".visualstudio.com", "dev.azure.com"))

    def _format_service_url(self, subdomain: str) -> str:
        base_url = self._organization_base_url
        if self._is_azure_devops_services():
            if ".visualstudio.com" in base_url:
                return base_url.replace(
                    ".visualstudio.com", f".{subdomain}.visualstudio.com"
                )
            return base_url.replace("dev.azure.com", f"{subdomain}.dev.azure.com")

        return base_url

    async def generate_users(
        self, additional_params: dict[str, str] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        users_url = (
            self._format_service_url("vsaex") + f"/{API_URL_PREFIX}/userentitlements"
        )
        params = dict(additional_params or {})
        api_version = params.get("api-version", "")

        if self._is_legacy_user_entitlements_version(api_version):
            async for users in self._get_paginated_by_top_and_skip(
                users_url,
                params=params,
                top_param="top",
                skip_param="skip",
            ):
                yield users
        else:
            async for users in self._get_paginated_by_top_and_continuation_token(
                users_url, data_key="items", additional_params=params
            ):
                yield users

    @staticmethod
    def _is_legacy_user_entitlements_version(api_version: str) -> bool:
        """Versions before 7.x use top/skip pagination and 'value' data key."""
        if not api_version:
            return False
        try:
            major = api_version.split(".")[0]
            return major.isdigit() and int(major) < 7
        except Exception:
            logger.warning(
                f"Failed to parse API version {api_version}, assuming legacy version"
            )
            return True

    async def generate_groups(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Generate all security groups in the organization."""
        async for batch in self._generate_groups_cached(self._organization_base_url):
            yield batch

    @cache_iterator_result()
    async def _generate_groups_cached(
        self, org_identifier: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        groups_url = (
            self._format_service_url("vssps") + f"/{API_URL_PREFIX}/graph/groups"
        )
        async for groups in self._get_paginated_by_top_and_continuation_token(
            groups_url
        ):
            yield groups

    async def _get_group_direct_members(
        self, group_descriptor: str
    ) -> Optional[list[dict[str, Any]]]:
        """Get direct members of a group."""
        members_url = (
            self._format_service_url("vssps")
            + f"/{API_URL_PREFIX}/graph/Memberships/{group_descriptor}"
        )
        response = await self.send_request(
            "GET", members_url, params={"direction": "Down"}
        )
        if not response:
            return None
        return response.json()["value"]

    async def _lookup_subjects(
        self, descriptors: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Batch lookup subject details for multiple descriptors."""
        all_results: dict[str, dict[str, Any]] = {}
        total_batches = (
            len(descriptors) + MAX_SUBJECTS_PER_LOOKUP - 1
        ) // MAX_SUBJECTS_PER_LOOKUP

        logger.info(
            f"Starting subject lookup for {len(descriptors)} descriptors across {total_batches} batch(es)"
        )

        for batch_num, batch in enumerate(
            batched(descriptors, MAX_SUBJECTS_PER_LOOKUP), start=1
        ):
            request_body = {"lookupKeys": [{"descriptor": d} for d in batch]}

            try:
                response = await self.send_request(
                    "POST",
                    self._format_service_url("vssps")
                    + f"/{API_URL_PREFIX}/graph/subjectlookup",
                    data=json.dumps(request_body),
                    headers={"Content-Type": "application/json"},
                    params={"api-version": "7.1-preview.1"},
                )

                if not response:
                    logger.warning(
                        f"No response received for subject lookup batch {batch_num} of {total_batches} (descriptors: {batch})"
                    )
                    continue
                all_results.update(response.json()["value"])

            except Exception as e:
                logger.warning(
                    f"Failed to look up subjects for batch {batch_num} of {total_batches} "
                    f"(size: {len(batch)}). Descriptors: {batch}. Error: {e}"
                )
                continue

        logger.info(f"Successfully looked up {len(all_results)} subjects")
        return all_results

    async def generate_group_members(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Generate direct group memberships (top-level only, no recursion).

        Yields members for each group. Each member includes:
        - __group: The full group object this member belongs to
        """
        async for groups in self.generate_groups():
            for group in groups:
                group_descriptor = group["descriptor"]

                memberships = await self._get_group_direct_members(group_descriptor)
                if not memberships:
                    logger.info(
                        f"No membership found for {group_descriptor}, skipping ..."
                    )
                    continue

                descriptors = [
                    membership["memberDescriptor"] for membership in memberships
                ]
                subject_details = await self._lookup_subjects(descriptors)

                members = []
                for membership in memberships:
                    member_descriptor = membership["memberDescriptor"]
                    if member_descriptor not in subject_details:
                        logger.debug(
                            f"Subject details not found for member '{member_descriptor}' in group '{group_descriptor}'"
                        )
                        continue
                    members.append(
                        {
                            **subject_details[member_descriptor],
                            "__group": group,
                        }
                    )

                logger.info(
                    f"Resolved {len(members)} direct members for group '{group_descriptor}'"
                )
                yield members

    async def _fetch_repositories_for_project(
        self,
        project: dict[str, Any],
        include_disabled_repositories: bool,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        repos_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/git/repositories"
        response = await self.send_request("GET", repos_url)
        if not response:
            return
        repositories = response.json()["value"]
        if include_disabled_repositories:
            yield repositories
        else:
            yield [repo for repo in repositories if self._repository_is_healthy(repo)]

    async def generate_repositories(
        self, include_disabled_repositories: bool = True
    ) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for batch in self._generate_repositories_cached(
            self._organization_base_url, include_disabled_repositories
        ):
            yield batch

    @cache_iterator_result()
    async def _generate_repositories_cached(
        self, org_identifier: str, include_disabled_repositories: bool = True
    ) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for projects in self.generate_projects():
            semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_PROJECTS)
            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    functools.partial(
                        self._fetch_repositories_for_project,
                        project,
                        include_disabled_repositories,
                    ),
                )
                for project in projects
            ]
            async for repositories in stream_async_iterators_tasks(*tasks):
                yield repositories

    async def generate_branches(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Generate branches for all repositories in all projects.

        API: GET {org}/{project}/_apis/git/repositories/{repoId}/refs?filter=heads/
        https://learn.microsoft.com/en-us/rest/api/azure/devops/git/refs/list?view=azure-devops-rest-7.1
        """
        async for repositories in self.generate_repositories(
            include_disabled_repositories=False
        ):
            semaphore = asyncio.BoundedSemaphore(
                MAX_CONCURRENT_REPOS_FOR_FILE_PROCESSING
            )
            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    functools.partial(
                        self._get_branches_for_repository,
                        repository,
                    ),
                )
                for repository in repositories
            ]
            async for branches in stream_async_iterators_tasks(*tasks):
                yield branches

    async def _get_branches_for_repository(
        self, repository: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get branches for a single repository."""
        project_id = repository["project"]["id"]
        repository_id = repository["id"]
        repository_name = repository["name"]

        branches_url = f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/git/repositories/{repository_id}/refs"
        params = {
            "filter": "heads/",
        }

        try:
            async for refs in self._get_paginated_by_top_and_continuation_token(
                branches_url, additional_params=params
            ):
                enriched_branches = []
                for ref in refs:
                    ref_name = ref["name"]
                    if ref_name.startswith("refs/heads/"):
                        branch_name = ref_name.replace("refs/heads/", "")

                        enriched_branch = {
                            "name": branch_name,
                            "refName": ref_name,
                            "objectId": ref["objectId"],
                            "__repository": repository,
                        }
                        enriched_branches.append(enriched_branch)

                if enriched_branches:
                    logger.info(
                        f"Found {len(enriched_branches)} branches for repository {repository_name}"
                    )
                    yield enriched_branches

        except Exception as e:
            logger.error(
                f"Failed to fetch branches for repository {repository_name} in project {project_id}: {str(e)}"
            )

    async def generate_pull_requests(
        self,
        search_filters: Optional[dict[str, Any]] = None,
        max_results: Optional[int] = None,
    ) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for repositories in self.generate_repositories(
            include_disabled_repositories=False
        ):
            semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_REPOS_FOR_PULL_REQUESTS)
            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    functools.partial(
                        self._get_paginated_by_top_and_skip,
                        f"{self._organization_base_url}/{repository['project']['id']}/{API_URL_PREFIX}/git/repositories/{repository['id']}/pullrequests",
                        search_filters,
                        max_results=max_results,
                    ),
                )
                for repository in repositories
            ]
            async for pull_requests in stream_async_iterators_tasks(*tasks):
                yield pull_requests

    async def generate_pipelines(self) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                pipelines_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/pipelines"
                async for (
                    pipelines
                ) in self._get_paginated_by_top_and_continuation_token(pipelines_url):
                    for pipeline in pipelines:
                        pipeline["__projectId"] = project["id"]
                    yield pipelines

    async def generate_releases(
        self,
        additional_params: dict[str, str] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                releases_url = (
                    self._format_service_url("vsrm")
                    + f"/{project['id']}/{API_URL_PREFIX}/release/releases"
                )
                async for releases in self._get_paginated_by_top_and_continuation_token(
                    releases_url, additional_params=additional_params or {}
                ):
                    yield releases

    async def generate_release_definitions(
        self,
        additional_params: dict[str, str] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                definitions_url = (
                    self._format_service_url("vsrm")
                    + f"/{project['id']}/{API_URL_PREFIX}/release/definitions"
                )
                async for (
                    definitions
                ) in self._get_paginated_by_top_and_continuation_token(
                    definitions_url, additional_params=additional_params or {}
                ):
                    for definition in definitions:
                        definition["__project"] = project
                    yield definitions

    async def generate_pipeline_runs(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Generate pipeline runs for all pipelines in all projects.

        API: GET {org}/{project}/_apis/pipelines/{pipelineId}/runs
        https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/list
        """
        async for projects in self.generate_projects():
            semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_PROJECTS)
            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    functools.partial(self._runs_for_project, project),
                )
                for project in projects
            ]
            async for batch in stream_async_iterators_tasks(*tasks):
                yield batch

    async def _runs_for_project(
        self, project: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield runs (in batches) for every pipeline in a given project."""
        async for pipelines in self._paginate_pipelines(project_id=project["id"]):
            if not pipelines:
                continue
            semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_PIPELINES)
            pipeline_tasks = [
                semaphore_async_iterator(
                    semaphore,
                    functools.partial(self._paginate_pipeline_runs, project, pipeline),
                )
                for pipeline in pipelines
            ]
            async for batch in stream_async_iterators_tasks(*pipeline_tasks):
                yield batch

    async def _paginate_pipelines(
        self, project_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Paginate pipelines for a project, yielding pipeline batches."""
        pipelines_url = (
            f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/pipelines"
        )
        async for pipelines in self._get_paginated_by_top_and_continuation_token(
            pipelines_url
        ):
            yield pipelines

    async def _paginate_pipeline_runs(
        self, project: dict[str, Any], pipeline: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Paginate runs for a specific pipeline, annotate each run
        with project/pipeline context, and yield batches.
        """
        runs_url = (
            f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}"
            f"/pipelines/{pipeline['id']}/runs"
        )
        async for runs in self._get_paginated_by_top_and_continuation_token(
            runs_url, data_key="value"
        ):
            if not runs:
                continue
            self.annotate_runs(runs, project=project, pipeline=pipeline)
            yield runs

    @staticmethod
    def annotate_runs(
        runs: Iterable[dict[str, Any]],
        project: dict[str, Any],
        pipeline: dict[str, Any],
    ) -> None:
        """Mutate each run to include project/pipeline metadata."""
        for run in runs:
            run["__project"] = project
            run["__pipeline"] = pipeline

    async def _fetch_stages_for_build(
        self, project: dict[str, Any], build: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fetch and process stage records for a specific build.

        Returns a list of stage records enriched with project and build context.
        Returns empty list if timeline fetch fails.
        """
        timeline_url = (
            f"{self._organization_base_url}/{project['id']}/"
            f"{API_URL_PREFIX}/build/builds/{build['id']}/timeline"
        )
        try:
            response = await self.send_request("GET", timeline_url)
            if not response:
                return []

            records = response.json().get("records", [])
            project_ref, build_ref = project, build

            stage_records = [
                {**record, "__project": project_ref, "__build": build_ref}
                for record in records
                if record.get("type") == "Stage"
            ]
            return stage_records

        except Exception as e:
            logger.warning(f"Failed to fetch timeline for build {build['id']}: {e}")
            return []

    def _enrich_builds_with_project_data(
        self,
        builds: list[dict[str, Any]],
        project: dict[str, Any],
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for build in builds:
            b = dict(build)
            b["__projectId"] = project["id"]
            b["__project"] = project
            enriched.append(b)
        return enriched

    async def _generate_builds_for_project(
        self,
        project: dict[str, Any],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield paginated builds for a single project, enriched with project data."""
        builds_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/build/builds"
        async for builds in self._get_paginated_by_top_and_continuation_token(
            builds_url,
            additional_params={"queryOrder": "queueTimeDescending"},
        ):
            yield self._enrich_builds_with_project_data(builds, project)

    async def generate_builds(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Generate builds across all projects in the organization.

        Uses continuation token pagination as per Azure DevOps Builds API.
        https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/list?view=azure-devops-rest-7.1
        """
        async for projects in self.generate_projects():
            tasks = [self._generate_builds_for_project(project) for project in projects]
            async for batch in stream_async_iterators_tasks(*tasks):
                yield batch

    async def generate_pipeline_stages(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Generate pipeline stages across all builds in the organization.

        Uses the Build Timeline API to fetch stage information for each build.
        https://learn.microsoft.com/en-us/rest/api/azure/devops/build/timeline/get?view=azure-devops-rest-7.1
        """
        async for projects in self.generate_projects():
            for project in projects:
                async for builds_batch in self._generate_builds_for_project(project):
                    semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_PIPELINES)

                    async def fetch_stages_with_semaphore(
                        build: dict[str, Any],
                    ) -> list[dict[str, Any]]:
                        async with semaphore:
                            return await self._fetch_stages_for_build(project, build)

                    stage_tasks = [
                        fetch_stages_with_semaphore(build) for build in builds_batch
                    ]
                    stage_results = await asyncio.gather(
                        *stage_tasks, return_exceptions=True
                    )

                    stages: list[dict[str, Any]] = []
                    for stage_records in stage_results:
                        if isinstance(stage_records, Exception):
                            logger.warning(f"Failed to fetch stages: {stage_records}")
                            continue
                        if stage_records and isinstance(stage_records, list):
                            stages.extend(stage_records)

                    if stages:
                        yield stages

    async def generate_iterations(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Generate iterations for all projects in the organization.

        API: GET {org}/{project}/_apis/wit/classificationnodes/iterations?$depth=2
        https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/classification-nodes/list?view=azure-devops-rest-7.1
        """
        async for projects in self.generate_projects():
            project_tasks = [
                self._iterations_for_project(project) for project in projects
            ]
            async for batch in stream_async_iterators_tasks(*project_tasks):
                yield batch

    async def _iterations_for_project(
        self, project: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield iterations (in batches) for a specific project."""
        project_id = project["id"]

        # Get teams for the project
        teams_url = f"{self._organization_base_url}/{API_URL_PREFIX}/projects/{project_id}/teams"

        try:
            teams_response = await self.send_request("GET", teams_url)
            if not teams_response:
                return

            teams = teams_response.json()["value"]

            # Process teams concurrently
            team_tasks = [
                self._get_iterations_for_team(project, team) for team in teams
            ]

            if team_tasks:
                team_results = await asyncio.gather(*team_tasks, return_exceptions=True)

                for result in team_results:
                    if isinstance(result, Exception):
                        logger.error(f"Failed to fetch team iterations: {result}")
                        continue
                    if result and isinstance(result, list):
                        yield result

        except Exception as e:
            logger.error(f"Failed to fetch teams for project {project_id}: {str(e)}")

    async def _get_iterations_for_team(
        self, project: dict[str, Any], team: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Get iterations for a specific team."""
        project_id = project["id"]
        team_id = team["id"]
        iterations_url = f"{self._organization_base_url}/{project_id}/{team_id}/{API_URL_PREFIX}/work/teamsettings/iterations"

        try:
            response = await self.send_request("GET", iterations_url, params=API_PARAMS)
            if not response:
                return []

            iterations_data = response.json()
            iterations = iterations_data.get("value", [])

            # Process and enrich iterations
            enriched_iterations = [
                {**iteration, "__project": project, "__team": team}
                for iteration in iterations
            ]

            return enriched_iterations

        except Exception as e:
            logger.error(
                f"Failed to fetch iterations for team {team_id} in project {project_id}: {str(e)}"
            )
            return []

    async def generate_area_paths(
        self, depth: Optional[int] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Generate area paths (work item area classification nodes) for all
        projects in the organization.
        """
        async for projects in self.generate_projects():
            project_tasks = [
                self._area_paths_for_project(project, depth) for project in projects
            ]
            async for batch in stream_async_iterators_tasks(*project_tasks):
                yield batch

    async def _area_paths_for_project(
        self, project: dict[str, Any], depth: Optional[int] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield the flattened area-path tree for a single project."""
        project_id = project["id"]
        areas_url = (
            f"{self._organization_base_url}/{project_id}"
            f"/{API_URL_PREFIX}/wit/classificationnodes/Areas"
        )
        params: dict[str, Any] = {**API_PARAMS}
        if depth is not None:
            params["$depth"] = depth

        try:
            response = await self.send_request("GET", areas_url, params=params)
            if not response:
                return

            area_paths = _flatten_area_path_tree(
                node=response.json(), project=project, parent_identifier=None
            )
            if area_paths:
                logger.info(
                    f"Found {len(area_paths)} area paths for project {project['name']}"
                )
                yield area_paths
        except Exception as e:
            logger.error(
                f"Failed to fetch area paths for project {project_id}: {str(e)}"
            )

    async def generate_environments(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._generate_environments_cached(
            self._organization_base_url
        ):
            yield batch

    @cache_iterator_result()
    async def _generate_environments_cached(
        self, org_identifier: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                environments_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/distributedtask/environments"
                async for (
                    environments
                ) in self._get_paginated_by_top_and_continuation_token(
                    environments_url
                ):
                    yield environments

    async def generate_release_deployments(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                deployments_url = (
                    self._format_service_url("vsrm")
                    + f"/{project['id']}/{API_URL_PREFIX}/release/deployments"
                )
                async for (
                    deployments
                ) in self._get_paginated_by_top_and_continuation_token(deployments_url):
                    yield deployments

    async def generate_pipeline_deployments(
        self, environment_id: int, project: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        deployments_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/distributedtask/environments/{environment_id}/environmentdeploymentrecords"
        async for deployments in self._get_paginated_by_top_and_continuation_token(
            deployments_url
        ):
            for deployment in deployments:
                deployment["__project"] = project
            yield deployments

    async def _fetch_policies_for_repo(
        self,
        repo: dict[str, Any],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params: dict[str, Any] = {
            "repositoryId": repo["id"],
        }
        if default_branch := repo.get("defaultBranch"):
            params["refName"] = default_branch

        policies_url = f"{self._organization_base_url}/{repo['project']['id']}/{API_URL_PREFIX}/git/policy/configurations"
        response = await self.send_request("GET", policies_url, params=params)
        if not response:
            return
        repo_policies = response.json()["value"]

        for policy in repo_policies:
            policy["__repository"] = repo
        yield repo_policies

    async def generate_repository_policies(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for repos in self.generate_repositories(
            include_disabled_repositories=False
        ):
            semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_REPOS_FOR_PULL_REQUESTS)
            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    functools.partial(self._fetch_policies_for_repo, repo),
                )
                for repo in repos
            ]
            async for policies in stream_async_iterators_tasks(*tasks):
                yield policies

    async def generate_work_items(
        self,
        wiql: Optional[str],
        expand: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieves a paginated list of work items within the Azure DevOps organization based on a WIQL query.

        Uses ID-range pagination to fetch all work items when a project exceeds the WIQL API limit
        of 20,000 results per query.
        """
        async for projects in self.generate_projects():
            for project in projects:
                # Execute WIQL queries with ID-range pagination to get all work item IDs
                async for work_item_ids in self._fetch_work_item_id_batches(
                    project, wiql
                ):
                    if not work_item_ids:
                        continue
                    logger.info(
                        f"Fetched batch of {len(work_item_ids)} work item IDs for project {project['name']}"
                    )
                    # Fetch work items using the IDs (in batches of 200 per API call)
                    async for work_items_batch in self._fetch_work_items_in_batches(
                        project["id"],
                        work_item_ids,
                        query_params={"$expand": expand},
                    ):
                        logger.debug(f"Received {len(work_items_batch)} work items")
                        # Enrich each work item with project details before yielding
                        yield self._add_project_details_to_work_items(
                            work_items_batch, project
                        )

    def _parse_wiql_with_order_by(
        self, wiql: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Parse user's WIQL into filter and ORDER BY parts.

        :param wiql: User-provided WIQL (filter conditions, optionally with ORDER BY).
        :return: Tuple of (filter_part, order_part). If no ORDER BY, order_part is None.
        """
        if not wiql or not wiql.strip():
            return None, None

        # Case-insensitive split on ORDER BY clause (WIQL: " ORDER BY [Field] Asc/Desc")
        wiql_stripped = wiql.strip()
        wiql_upper = wiql_stripped.upper()
        order_by_marker = " ORDER BY "
        order_by_idx = wiql_upper.find(order_by_marker)
        if order_by_idx == -1:
            # Also check for ORDER BY at start (no leading space)
            if wiql_upper.startswith("ORDER BY "):
                order_part = wiql_stripped[len("ORDER BY ") :].strip()
                return None, order_part or None
            return wiql_stripped, None

        filter_part = wiql_stripped[:order_by_idx].strip()
        order_part = wiql_stripped[order_by_idx + len(order_by_marker) :].strip()
        return filter_part or None, order_part or None

    async def _fetch_work_item_id_batches(
        self, project: dict[str, Any], wiql: Optional[str]
    ) -> AsyncGenerator[list[int], None]:
        """
        Executes WIQL queries to fetch work item IDs for a project.

        When user's WIQL has no ORDER BY: uses ID-range pagination to fetch all work items
        (Azure DevOps WIQL API returns at most 20,000 per query).

        When user's WIQL has ORDER BY: uses their query as-is. Pagination is disabled;
        only up to 20,000 work items per project will be returned (with a warning).

        :param project: The project dict containing id and name.
        :param wiql: Optional user-provided WIQL filter to append to the WHERE clause.
        :yield: Batches of work item IDs (each batch up to MAX_WORK_ITEMS_RESULTS_PER_PROJECT).
        """
        filter_part, user_order_part = self._parse_wiql_with_order_by(wiql)

        wiql_base = f"SELECT [Id] FROM WorkItems WHERE [System.TeamProject] = '{project['name']}'"
        if filter_part:
            wiql_base += f" AND ({filter_part})"
            logger.info(f"Using WIQL filter: {filter_part}")

        if user_order_part:
            logger.warning(
                "WIQL contains ORDER BY. Pagination is disabled - only up to 20,000 work items "
                "per project will be returned. To fetch all work items, remove ORDER BY from your WIQL."
            )
            # Single WIQL call, no pagination loop
            wiql_query = wiql_base + f" ORDER BY {user_order_part}"
            wiql_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/wit/wiql"
            wiql_response = await self.send_request(
                "POST",
                wiql_url,
                params={
                    "api-version": "7.1-preview.2",
                    "$top": MAX_WORK_ITEMS_RESULTS_PER_PROJECT,
                },
                data=json.dumps({"query": wiql_query}),
                headers={"Content-Type": "application/json"},
            )
            if wiql_response:
                work_items = wiql_response.json().get("workItems", [])
                work_item_ids = [item["id"] for item in work_items]
                if work_item_ids:
                    yield work_item_ids
            return

        # No user ORDER BY: use our ORDER BY [System.Id] Asc for pagination
        wiql_url = (
            f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/wit/wiql"
        )
        last_id = 0

        while True:
            wiql_query = wiql_base
            if last_id > 0:
                wiql_query += f" AND [System.Id] > {last_id}"
            wiql_query += " ORDER BY [System.Id] Asc"

            logger.debug(
                f"Fetching work item IDs for project {project['name']} (last_id={last_id})"
            )
            wiql_response = await self.send_request(
                "POST",
                wiql_url,
                params={
                    "api-version": "7.1-preview.2",
                    "$top": MAX_WORK_ITEMS_RESULTS_PER_PROJECT,
                },
                data=json.dumps({"query": wiql_query}),
                headers={"Content-Type": "application/json"},
            )
            if not wiql_response:
                break

            work_items = wiql_response.json().get("workItems", [])
            work_item_ids = [item["id"] for item in work_items]

            if not work_item_ids:
                break

            yield work_item_ids

            if len(work_item_ids) < MAX_WORK_ITEMS_RESULTS_PER_PROJECT:
                logger.info(
                    f"Completed work item ID fetch for project {project['name']} "
                    f"(total batches, last batch had {len(work_item_ids)} items)"
                )
                break

            last_id = max(work_item_ids)

    async def _fetch_work_items_in_batches(
        self,
        project_id: str,
        work_item_ids: list[int],
        query_params: dict[str, Any] = {},
        page_size: int = MAX_WORK_ITEMS_PER_REQUEST,  # default to API maximum if not overridden
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetches work items in batches from the given list of work item IDs.

        :param project_id: The project ID.
        :param work_item_ids: List of work item IDs to fetch.
        :param query_params: Additional query parameters (e.g., for expansion).
        :param page_size: Number of work items to request per API call.
        :yield: A list (batch) of work items.
        """
        number_of_batches = len(work_item_ids) // page_size
        logger.info(
            f"Fetching work items in {number_of_batches} batches with {page_size} work items per batch for project {project_id}"
        )
        for i in range(0, len(work_item_ids), page_size):
            batch_ids = work_item_ids[i : i + page_size]
            if not batch_ids:
                continue
            logger.debug(
                f"Processing batch {i // page_size + 1}/{number_of_batches} with {len(batch_ids)} work items for project {project_id}"
            )
            work_items_url = f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/wit/workitems"
            params = {
                **query_params,
                "ids": ",".join(map(str, batch_ids)),
                "api-version": "7.1-preview.3",
            }
            work_items_response = await self.send_request(
                "GET", work_items_url, params=params
            )
            if not work_items_response:
                continue
            try:
                yield work_items_response.json()["value"]
            except json.decoder.JSONDecodeError as e:
                logger.error(
                    f"Failed to decode work items response for project {project_id}, "
                    f"batch IDs {batch_ids[0]}-{batch_ids[-1]} ({len(batch_ids)} items): {e}. "
                    f"Aborting resync to prevent incorrect deletes of work items in incomplete batch."
                )
                raise

    def _add_project_details_to_work_items(
        self, work_items: list[dict[str, Any]], project: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Adds the project ID to each work item in the list.

        :param work_items: List of work items to modify.
        :param project_id: The project ID to add to each work item.
        """
        for work_item in work_items:
            work_item["__projectId"] = project["id"]
            work_item["__project"] = project
        return work_items

    async def get_work_item(
        self, project_id: str, work_item_id: int, expand: str = "All"
    ) -> Optional[dict[str, Any]]:
        """
        Fetches a single work item by ID from Azure DevOps.

        :param project_id: The project ID containing the work item.
        :param work_item_id: The work item ID to fetch.
        :param expand: Expand options for work items. Allowed values are 'None', 'Fields', 'Relations', 'Links' and 'All'. Default value is 'All'.
        :return: The work item data or None if not found.
        """
        work_item_url = f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/wit/workitems/{work_item_id}"
        params = {
            "api-version": API_PARAMS["api-version"],
            "$expand": expand,
        }
        response = await self.send_request("GET", work_item_url, params=params)
        if not response:
            return None
        return response.json()

    async def get_pull_request(self, pull_request_id: str) -> dict[Any, Any] | None:
        get_single_pull_request_url = f"{self._organization_base_url}/{API_URL_PREFIX}/git/pullrequests/{pull_request_id}"
        response = await self.send_request("GET", get_single_pull_request_url)
        if not response:
            return None
        pull_request_data = response.json()
        return pull_request_data

    async def get_repository(self, repository_id: str) -> dict[Any, Any] | None:
        get_single_repository_url = f"{self._organization_base_url}/{API_URL_PREFIX}/git/repositories/{repository_id}"
        response = await self.send_request("GET", get_single_repository_url)
        if not response:
            return None
        repository_data = response.json()
        return repository_data

    async def get_pipeline(
        self, project_id: str, pipeline_id: str
    ) -> dict[Any, Any] | None:
        get_single_pipeline_url = f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/pipelines/{pipeline_id}"
        response = await self.send_request("GET", get_single_pipeline_url)
        if not response:
            return None
        pipeline_data = response.json()
        return pipeline_data

    async def get_pipeline_run(
        self, project_id: str, pipeline_id: str, run_id: str
    ) -> dict[Any, Any] | None:
        get_single_pipeline_run_url = (
            f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}"
            f"/pipelines/{pipeline_id}/runs/{run_id}"
        )
        response = await self.send_request("GET", get_single_pipeline_run_url)
        if not response:
            return None
        pipeline_run_data = response.json()
        return pipeline_run_data

    async def get_pipeline_stage(
        self, project: dict[str, Any], pipeline_id: str, run_id: str, stage_id: str
    ) -> dict[Any, Any] | None:
        pipeline_run = await self.get_pipeline_run(project["id"], pipeline_id, run_id)
        if not pipeline_run:
            return None

        stages = await self._fetch_stages_for_build(project, pipeline_run)
        if not stages:
            return None

        for stage in stages:
            if stage["id"] == stage_id:
                return stage
        return None

    async def get_release(
        self, project_id: str, release_id: int
    ) -> dict[Any, Any] | None:
        release_url = (
            self._format_service_url("vsrm")
            + f"/{project_id}/{API_URL_PREFIX}/release/releases/{release_id}"
        )
        response = await self.send_request("GET", release_url)
        if not response:
            return None
        return response.json()

    async def get_release_definition(
        self, project_id: str, definition_id: str, project: dict[str, Any]
    ) -> dict[Any, Any] | None:
        definition_url = (
            self._format_service_url("vsrm")
            + f"/{project_id}/{API_URL_PREFIX}/release/definitions/{definition_id}"
        )
        response = await self.send_request("GET", definition_url)
        if not response:
            return None
        definition = response.json()
        definition["__project"] = project
        return definition

    async def get_release_deployment(
        self, project_id: str, release_id: int, environment_id: int
    ) -> dict[Any, Any] | None:
        deployments_url = (
            self._format_service_url("vsrm")
            + f"/{project_id}/{API_URL_PREFIX}/release/deployments"
        )
        params = {
            "deploymentStatus": "all",
            "releaseId": release_id,
            "definitionEnvironmentId": environment_id,
            "$top": 1,
        }
        response = await self.send_request("GET", deployments_url, params=params)
        if not response:
            return None
        deployments = response.json().get("value", [])
        return deployments[0] if deployments else None

    async def get_columns(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for boards in self.get_boards_in_organization():
            for board in boards:
                yield [
                    {
                        **column,
                        "__board": board,
                        "__stateType": stateType,
                        "__stateName": stateName,
                    }
                    for column in board.get("columns", [])
                    if column.get("stateMappings")
                    for stateType, stateName in column.get("stateMappings").items()
                ]

    async def _enrich_boards(
        self, boards: list[dict[str, Any]], project_id: str, team_id: str
    ) -> list[dict[str, Any]]:
        for board in boards:
            url = f"{self._organization_base_url}/{project_id}/{team_id}/{API_URL_PREFIX}/work/boards/{board['id']}"
            response = await self.send_request(
                "GET",
                url,
            )
            if not response:
                continue
            board.update(response.json())
        return boards

    async def _get_boards(
        self, project_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        teams_url = f"{self._organization_base_url}/{API_URL_PREFIX}/projects/{project_id}/teams"
        async for teams_in_project in self._get_paginated_by_top_and_skip(teams_url):
            for team in teams_in_project:
                try:
                    get_boards_url = f"{self._organization_base_url}/{project_id}/{team['id']}/{API_URL_PREFIX}/work/boards"
                    response = await self.send_request("GET", get_boards_url)
                    if not response:
                        continue

                    board_data = response.json().get("value", [])
                    if not board_data:
                        continue

                    logger.info(
                        f"Found {len(board_data)} boards for project {project_id}"
                    )
                    yield await self._enrich_boards(board_data, project_id, team["id"])

                except HTTPStatusError as e:
                    # Azure Devops API throws 500 errors when you try to fetch boards for teams that
                    # are not in a sprint iteration. We should skip those.
                    if e.response.status_code == 500:
                        logger.warning(
                            f"Skipping board fetch for team {team['id']} in project {project_id} due to a server error (HTTP 500). "
                            "This can occur if the team is not assigned to an iteration."
                        )
                        continue
                    raise

    async def get_boards_in_organization(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self._get_boards_in_organization_cached(
            self._organization_base_url
        ):
            yield batch

    @cache_iterator_result()
    async def _get_boards_in_organization_cached(
        self, org_identifier: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.generate_projects():
            yield [
                {**board, "__project": project}
                for project in projects
                async for boards in self._get_boards(project["id"])
                for board in boards
            ]

    async def generate_subscriptions_webhook_events(
        self,
        publisher_id: str,
        event_type: str,
    ) -> list[WebhookSubscription]:
        headers = {"Content-Type": "application/json"}
        params: dict[str, str] = {
            "publisherId": publisher_id,
            "eventType": event_type,
        }
        try:
            get_subscriptions_url = (
                f"{self._organization_base_url}/{API_URL_PREFIX}/hooks/subscriptions"
            )
            response = await self.send_request(
                "GET", get_subscriptions_url, headers=headers, params=params
            )
            if not response:
                return []
            subscriptions_raw = response.json().get("value", [])
        except json.decoder.JSONDecodeError:
            err_str = "Couldn't decode response from subscritions route. This may be because you are unauthorized- Check PAT (Personal Access Token) validity"
            logger.warning(err_str)
            raise Exception(err_str)
        return [
            WebhookSubscription(**subscription) for subscription in subscriptions_raw
        ]

    async def get_filtered_webhook_subscriptions(
        self,
    ) -> list[WebhookSubscription]:
        unique_filters = {
            (sub.publisherId, sub.eventType)
            for sub in AZURE_DEVOPS_WEBHOOK_SUBSCRIPTIONS
        }
        semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_SUBSCRIPTION_REQUESTS)

        async def fetch(
            publisher_id: str, event_type: str
        ) -> list[WebhookSubscription]:
            async with semaphore:
                logger.debug(
                    f"Fetching existing subscriptions for publisherId={publisher_id}, eventType={event_type}"
                )
                return await self.generate_subscriptions_webhook_events(
                    publisher_id=publisher_id, event_type=event_type
                )

        results = await asyncio.gather(
            *[fetch(pub_id, evt_type) for pub_id, evt_type in unique_filters],
            return_exceptions=True,
        )

        subscriptions: list[WebhookSubscription] = []
        for result in results:
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, BaseException):
                logger.warning(f"Failed to fetch webhook subscriptions: {result}")
                continue
            subscriptions.extend(result)
        return subscriptions

    async def create_subscription(
        self,
        webhook_subscription: WebhookSubscription,
    ) -> Optional[str]:
        """Create a webhook subscription and return its ID (or None on failure)."""
        headers = {"Content-Type": "application/json"}
        subscription_base_url = self._organization_base_url
        params = WEBHOOK_API_PARAMS
        if webhook_subscription.publisherId == ADVANCED_SECURITY_PUBLISHER_ID:
            subscription_base_url = self._advsec_base_url
            params = ADVANCED_SECURITY_API_PARAMS
        elif webhook_subscription.publisherId == RELEASE_PUBLISHER_ID:
            subscription_base_url = self._format_service_url("vsrm")

        create_subscription_url = (
            f"{subscription_base_url}/{API_URL_PREFIX}/hooks/subscriptions"
        )
        webhook_subscription_json = webhook_subscription.json()
        logger.info(f"Creating subscription to event: {webhook_subscription_json}")
        response = await self.send_request(
            "POST",
            create_subscription_url,
            params=params,
            headers=headers,
            data=webhook_subscription_json,
        )
        if not response:
            return None
        response_content = response.json()
        sub_id = response_content.get("id")
        logger.info(
            f"Created subscription id: {sub_id} for eventType {response_content.get('eventType')}"
        )
        return sub_id

    async def delete_subscription(
        self, webhook_subscription: WebhookSubscription
    ) -> None:
        headers = {"Content-Type": "application/json"}
        subscription_base_url = self._organization_base_url
        params = WEBHOOK_API_PARAMS
        if webhook_subscription.publisherId == ADVANCED_SECURITY_PUBLISHER_ID:
            subscription_base_url = self._advsec_base_url
            params = ADVANCED_SECURITY_API_PARAMS
        elif webhook_subscription.publisherId == RELEASE_PUBLISHER_ID:
            subscription_base_url = self._format_service_url("vsrm")

        delete_subscription_url = f"{subscription_base_url}/{API_URL_PREFIX}/hooks/subscriptions/{webhook_subscription.id}"
        logger.info(f"Deleting subscription to event: {webhook_subscription.json()}")
        await self.send_request(
            "DELETE",
            delete_subscription_url,
            headers=headers,
            params=params,
        )

    async def _get_item_content(
        self, file_path: str, repository_id: str, version_type: str, version: str
    ) -> bytes:
        items_params = {
            "versionType": version_type,
            "version": version,
            "path": file_path,
        }
        items_url = f"{self._organization_base_url}/{API_URL_PREFIX}/git/repositories/{repository_id}/items"
        try:
            logger.info(
                f"Getting file {file_path} from repo id {repository_id} by {version_type}: {version}"
            )

            response = await self.send_request(
                method="GET", url=items_url, params=items_params
            )
            if not response:
                logger.warning(
                    f"Failed to access URL '{items_url}'. The repository '{repository_id}' might be disabled or inaccessible."
                )
                return bytes()
            file_content = response.content
        except HTTPStatusError as e:
            general_err_msg = f"Couldn't fetch file {file_path} from repo id {repository_id}: {str(e)}. Returning empty file."
            logger.warning(general_err_msg)
            return bytes()
        except Exception as e:
            logger.warning(
                f"Couldn't fetch file {file_path} from repo id {repository_id}: {str(e)}. Returning empty file."
            )
            return bytes()
        else:
            return file_content

    async def get_file_by_branch(
        self, file_path: str, repository_id: str, branch_name: str
    ) -> bytes:
        return await self._get_item_content(
            file_path, repository_id, "Branch", branch_name
        )

    async def get_file_by_commit(
        self, file_path: str, repository_id: str, commit_id: str
    ) -> bytes:
        return await self._get_item_content(
            file_path, repository_id, "Commit", commit_id
        )

    async def generate_files(
        self,
        path: str | list[str],
        repos: Optional[list[str]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        paths = [path] if isinstance(path, str) else path
        logger.info(f"Processing files with paths: {paths}")

        async for repositories in self.generate_repositories(
            include_disabled_repositories=True
        ):
            if not repositories:
                logger.warning(
                    "Skipping file discovery for project with no repositories."
                )
                continue

            filtered_repositories = (
                [repo for repo in repositories if repo["name"] in repos]
                if repos
                else repositories
            )

            semaphore = asyncio.BoundedSemaphore(
                MAX_CONCURRENT_REPOS_FOR_FILE_PROCESSING
            )

            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    functools.partial(self._get_repository_files, repository, paths),
                )
                for repository in filtered_repositories
            ]

            async for batch in stream_async_iterators_tasks(*tasks):
                yield batch

    async def _get_repository_files(
        self,
        repository: dict[str, Any],
        paths: list[str],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(
            f"Checking repository {repository['name']} for files matching {paths}"
        )

        branch = repository.get("defaultBranch")
        if not branch:
            logger.warning(
                f"Repository {repository['name']} has no default branch. Skipping."
            )
            return

        branch = branch.replace("refs/heads/", "")

        files = []
        literal_paths, glob_patterns = separate_glob_and_literal_paths(paths)

        if literal_paths:
            files += await self._get_files_by_explicit_paths(
                repository, literal_paths, branch
            )

        if glob_patterns:
            descriptors = [extract_descriptor_from_pattern(p) for p in glob_patterns]
            grouped = group_descriptors_by_base(descriptors)

            for base_path, group in grouped.items():
                recursion = sorted({d.recursion for d in group}, key=get_priority)[-1]

                # Fetch files once for the base path with the highest recursion level
                descriptor = PathDescriptor(
                    base_path=base_path,
                    recursion=recursion,
                    pattern=group[0].pattern,
                )
                raw_files = await self._get_files_by_descriptors(
                    repository, [descriptor], branch
                )

                # Match files against all patterns in the group
                for pattern_desc in group:
                    matched = filter_files_by_glob(raw_files, pattern_desc)
                    files += matched

        logger.info(f"Found {len(files)} files in repository {repository['name']}")

        downloaded_files = await process_in_queue(
            files,
            self.download_single_file,
            repository,
            branch,
            concurrency=MAX_CONCURRENT_FILE_DOWNLOADS,
        )

        for file in downloaded_files:
            if file is None:
                logger.warning(
                    f"A file in repository {repository['name']} could not be downloaded or processed and will be skipped."
                )
                continue
            yield [file]

    async def _get_files_by_explicit_paths(
        self,
        repository: dict[str, Any],
        paths: list[str],
        branch: str,
    ) -> list[dict[str, Any]]:
        item_descriptors = [
            PathDescriptor(
                base_path=path if path.startswith("/") else f"/{path}",
                recursion=RecursionLevel.NONE,
                pattern=path,
            )
            for path in paths
        ]
        return await self._get_files_by_descriptors(
            repository, item_descriptors, branch
        )

    async def _get_files_by_descriptors(
        self,
        repository: dict[str, Any],
        descriptors: list[PathDescriptor],
        branch: str,
    ) -> list[dict[str, Any]]:
        project_id = repository["project"]["id"]
        repository_id = repository["id"]
        items_batch_url = f"{self._organization_base_url}/{project_id}/_apis/git/repositories/{repository_id}/itemsbatch"

        request_data = {
            "itemDescriptors": [
                {
                    "path": d.base_path,
                    "recursionLevel": d.recursion,
                    "version": branch,
                    "versionType": "branch",
                }
                for d in descriptors
            ]
        }

        transient_retries = 0
        while transient_retries <= MAX_TIMEMOUT_RETRIES:
            try:
                response = await self.send_request(
                    "POST",
                    items_batch_url,
                    params=API_PARAMS,
                    data=json.dumps(request_data),
                    headers={"Content-Type": "application/json"},
                )
                if not response:
                    logger.warning(f"Failed to fetch items from {items_batch_url}")
                    return []

                batch_results = response.json()
                return [
                    file
                    for sublist in batch_results.get("value", [])
                    for file in sublist
                ]

            except ReadTimeout:
                transient_retries += 1
                if transient_retries <= MAX_TIMEMOUT_RETRIES:
                    logger.warning(
                        f"Request timeout while fetching items for repository {repository['name']} "
                        f"(attempt {transient_retries}/{MAX_TIMEMOUT_RETRIES + 1}). Retrying..."
                    )
                    await asyncio.sleep(2 ** (transient_retries - 1))
                    continue
                else:
                    logger.error(
                        f"Request timeout while fetching items for repository {repository['name']} "
                        f"after {MAX_TIMEMOUT_RETRIES + 1} attempts. Skipping repository update to prevent "
                        f"false deletions. This should be reported as a bug for further investigation."
                    )
                    raise TimeoutError(
                        f"Persistent timeout fetching files for repository {repository['name']}. "
                        f"Skipping update to prevent false entity deletions."
                    )

            except HTTPStatusError as e:
                if e.response.status_code == 503:
                    transient_retries += 1
                    if transient_retries <= MAX_TIMEMOUT_RETRIES:
                        logger.warning(
                            f"503 from itemsbatch for repository {repository['name']} "
                            f"(attempt {transient_retries}/{MAX_TIMEMOUT_RETRIES + 1}). Retrying..."
                        )
                        await asyncio.sleep(2 ** (transient_retries - 1))
                        continue
                    logger.error(
                        f"Persistent 503 fetching items for repository {repository['name']} "
                        f"after {MAX_TIMEMOUT_RETRIES + 1} attempts."
                    )
                    raise
                logger.error(e.response.status_code)
                logger.error(e.response.text)
                if e.response.status_code == 400:
                    logger.warning(
                        f"None of the paths {', '.join([d.pattern for d in descriptors])} were found in repository {repository['name']}"
                    )
                    return []
                raise
            except Exception as e:
                logger.error(
                    f"Unexpected error processing files in {repository['name']}: {e}"
                )
                raise

        raise RuntimeError(
            f"Failed to fetch files for repository {repository['name']} after all retry attempts"
        )

    async def download_single_file(
        self, file: dict[str, Any], repository: dict[str, Any], branch: str
    ) -> dict[str, Any] | None:
        if not file:
            return None

        if file.get("gitObjectType") != "blob":
            return None

        file_path = file["path"].lstrip("/")
        content = await self.get_file_by_branch(file_path, repository["id"], branch)

        if not content:
            return None

        file_size = len(content)
        if file_size > MAX_ALLOWED_FILE_SIZE_IN_BYTES:
            logger.warning(f"Skipping large file {file_path} ({file_size} bytes)")
            return None

        file_obj = {
            "path": file_path,
            "objectId": file["objectId"],
            "size": file_size,
            "isFolder": False,
            "commitId": file.get("commitId"),
            **file.get("contentMetadata", {}),
        }

        try:
            parsed_content = await parse_file_content(content)
            processed_file = {
                "file": {
                    **file_obj,
                    "content": {
                        "raw": content.decode("utf-8"),
                        "parsed": parsed_content,
                    },
                    "size": len(content),
                },
                "repo": repository,
            }
            logger.info(
                f"Downloaded file {file_path} of size {file_size} bytes "
                f"({file_size / 1024:.2f} KB, {file_size / (1024 * 1024):.2f} MB)"
            )
            return processed_file
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {str(e)}")
            raise

    async def get_commit_changes(
        self, project_id: str, repository_id: str, commit_id: str
    ) -> dict[str, Any]:
        try:
            url = f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/git/repositories/{repository_id}/commits/{commit_id}/changes"
            response = await self.send_request("GET", url, params=API_PARAMS)
            return response.json() if response else {}
        except Exception as e:
            logger.error(f"Failed to commit changes from {url}: {str(e)}")
            raise

    async def create_webhook_subscriptions(
        self,
        base_url: str,
        project_id: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        existing_subscriptions: Optional[list[WebhookSubscription]] = None,
    ) -> list[str]:
        """Create/reconcile webhook subscriptions and return all active subscription IDs."""
        auth_username = self.webhook_auth_username

        if existing_subscriptions is None:
            existing_subscriptions = await self.get_filtered_webhook_subscriptions()

        subs_to_create = []
        subs_to_delete = []
        # IDs of existing healthy subscriptions we keep as-is — needed for
        # the subscription registry so incoming events can be routed.
        kept_sub_ids: list[str] = []

        webhook_subs = AZURE_DEVOPS_WEBHOOK_SUBSCRIPTIONS

        for sub in webhook_subs:
            sub.set_webhook_details(
                url=f"{base_url}{WEBHOOK_URL_SUFFIX}",
                auth_username=auth_username,
                webhook_secret=webhook_secret,
                project_id=project_id,
            )
            existing_sub = sub.get_event_by_subscription(existing_subscriptions)

            if existing_sub and not existing_sub.is_enabled():
                # Disabled subscription — recreate it.
                subs_to_delete.append(existing_sub)
                subs_to_create.append(sub)
            elif existing_sub and existing_sub.id:
                kept_sub_ids.append(existing_sub.id)
            elif not existing_sub:
                subs_to_create.append(sub)

        if subs_to_delete:
            await asyncio.gather(
                *[self.delete_subscription(sub) for sub in subs_to_delete]
            )

        created_sub_ids: list[str] = []
        if subs_to_create:
            semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_SUBSCRIPTION_REQUESTS)

            async def create(subscription: WebhookSubscription) -> Optional[str]:
                async with semaphore:
                    return await self.create_subscription(subscription)

            results = await asyncio.gather(
                *[create(sub) for sub in subs_to_create],
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Exception):
                    logger.error(
                        f"Failed to create webhook: {type(result).__name__}: {result}"
                    )
                elif isinstance(result, str):
                    created_sub_ids.append(result)

        # Return all active subscription IDs so the caller can populate the
        # subscription registry for webhook event routing.
        return kept_sub_ids + created_sub_ids

    async def get_repository_tree(
        self,
        repository_id: str,
        recursion_level: str,  # Options: none, oneLevel, full
        path: str = "/",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch repository folder structure with rate limit awareness.

        Args:
            repository_id: The ID of the repository to scan
            path: The folder path to start scanning from
            recursion_level: How deep to scan (none, oneLevel, full)

        Yields:
            Lists of folder information dictionaries
        """
        items_batch_url = f"{self._organization_base_url}/_apis/git/repositories/{repository_id}/items"

        params = {
            "scopePath": path,
            "recursionLevel": recursion_level,
            "$top": PAGE_SIZE,
            "api-version": "7.1",
        }

        try:
            async for items in self._get_paginated_by_top_and_continuation_token(
                items_batch_url, additional_params=params
            ):
                # Filter for folders only
                folders = [
                    item for item in items if item.get("gitObjectType") == "tree"
                ]

                if folders:
                    yield folders

        except Exception as e:
            logger.error(
                f"Error fetching folder tree for repository {repository_id}: {str(e)}"
            )
            raise

    def _build_tree_fetcher(
        self,
        repository_id: str,
        pattern: str,
    ) -> Callable[[], AsyncGenerator[list[dict[str, Any]], None]]:
        # Get the base path (everything before the first wildcard)
        parts = pattern.split("/")
        base_parts = []
        for part in parts:
            if "*" not in part:
                base_parts.append(part)
            else:
                break
        base_path = "/".join(base_parts)

        return functools.partial(
            self.get_repository_tree,
            repository_id,
            path=base_path or "/",
            recursion_level="oneLevel",  # Always use oneLevel recursion
        )

    async def get_repository_folders(
        self,
        repository_id: str,
        folder_patterns: list[str],
        concurrency: int = 5,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get folders matching patterns with concurrency control.

        Args:
            repository_id: The ID of the repository to scan
            folder_patterns: List of folder paths to scan (supports * wildcard only)
            concurrency: Maximum number of concurrent requests

        Yields:
            Lists of folder information dictionaries
        """
        semaphore = asyncio.BoundedSemaphore(concurrency)

        tasks = [
            semaphore_async_iterator(
                semaphore, self._build_tree_fetcher(repository_id, pattern)
            )
            for pattern in folder_patterns
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            matching_folders = []
            for folder in batch:
                # For each folder in the batch, check if it matches any of our patterns
                for pattern in folder_patterns:
                    folder_path = folder.get("path", "").strip("/")
                    pattern = pattern.strip("/")
                    # Check if path depth matches and pattern matches
                    if folder_path.count("/") == pattern.count("/") and fnmatch.fnmatch(
                        folder_path, pattern
                    ):
                        matching_folders.append(folder)
            if matching_folders:
                yield matching_folders

    async def _process_pattern(
        self,
        repo: dict[str, Any],
        folder_pattern: FolderPattern,
        repo_mapping: RepositoryBranchMapping | None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        branch = repo_mapping.branch if repo_mapping else None
        if not branch and "defaultBranch" in repo:
            branch = repo["defaultBranch"].replace("refs/heads/", "")

        async for found_folders in self.get_repository_folders(
            repo["id"], [folder_pattern.path]
        ):
            processed_folders = []
            for folder in found_folders:
                folder_dict = dict(folder)
                folder_dict["__repository"] = repo
                folder_dict["__branch"] = branch
                folder_dict["__pattern"] = folder_pattern.path
                processed_folders.append(folder_dict)
            if processed_folders:
                yield processed_folders

    async def _process_repository_folder_patterns(
        self,
        repo: dict[str, Any],
        repo_pattern_map: dict[
            str, list[tuple[FolderPattern, RepositoryBranchMapping | None]]
        ],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        repo_name = repo["name"]
        if repo_name not in repo_pattern_map:
            return

        matching_patterns = repo_pattern_map[repo_name]
        tasks = [
            self._process_pattern(repo, folder_pattern, repo_mapping)
            for folder_pattern, repo_mapping in matching_patterns
        ]

        async for result in stream_async_iterators_tasks(*tasks):
            yield result

    async def get_repository_by_name(
        self, project_name: str, repo_name: str
    ) -> dict[str, Any] | None:
        """Get a single repository by name using Azure DevOps API."""
        repo_url = f"{self._organization_base_url}/{project_name}/{API_URL_PREFIX}/git/repositories/{repo_name}"
        response = await self.send_request(
            "GET", repo_url, params={"api-version": "7.1"}
        )
        if not response:
            return None
        return response.json()

    async def _get_repositories_for_project(
        self, project_name: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get repositories for a specific project."""
        project = await self.get_single_project(project_name)
        if not project:
            logger.warning(f"Project {project_name} not found")
            return

        repos_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/git/repositories"
        repos_response = await self.send_request("GET", repos_url)
        if repos_response:
            yield repos_response.json()["value"]

    async def process_folder_patterns(
        self,
        folder_patterns: list[FolderPattern],
        project_name: str | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Process folder patterns and yield matching folders with optimized performance.

        Args:
            folder_patterns: List of folder patterns to process
            project_name: The project name (optional). If None, syncs from all projects.
        """
        # Create a mapping of repository names to their patterns
        repo_pattern_map: dict[
            str, list[tuple[FolderPattern, RepositoryBranchMapping | None]]
        ] = defaultdict(list)
        global_patterns: list[FolderPattern] = []

        for pattern in folder_patterns:
            if not pattern.repos:
                global_patterns.append(pattern)
            else:
                for repo_mapping in pattern.repos:
                    repo_pattern_map[repo_mapping.name].append((pattern, repo_mapping))

        tasks = []
        repositories = (
            self._get_repositories_for_project(project_name)
            if project_name
            else self.generate_repositories()
        )

        async for repo_batch in repositories:
            for repo in repo_batch:
                # Check if repo has specific patterns
                if repo["name"] in repo_pattern_map:
                    tasks.append(
                        self._process_repository_folder_patterns(
                            repo, {repo["name"]: repo_pattern_map[repo["name"]]}
                        )
                    )
                # Apply global patterns to all repos
                elif global_patterns:
                    tasks.append(
                        self._process_repository_folder_patterns(
                            repo,
                            {repo["name"]: [(gp, None) for gp in global_patterns]},
                        )
                    )

        async for result in stream_async_iterators_tasks(*tasks):
            yield result

    async def enrich_pipelines_with_repository(
        self, pipelines: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Enrich pipelines with repository information."""

        url_template = f"{self._organization_base_url}/{{project_id}}/{API_URL_PREFIX}/build/definitions/{{pipeline_id}}"

        tasks = [
            self.send_request(
                "GET",
                url_template.format(
                    project_id=pipeline["__projectId"], pipeline_id=pipeline["id"]
                ),
            )
            for pipeline in pipelines
        ]
        results = await asyncio.gather(*tasks)
        definitions = []
        for resp in results:
            if resp is not None:
                definitions.append(resp.json())

        enriched = []
        for pipeline, definition in zip(pipelines, definitions):
            pipeline["__repository"] = {
                **definition["repository"],
                "project": definition["project"],
            }
            enriched.append(pipeline)

        return enriched

    async def _fetch_enriched_test_runs(
        self,
        project_id: str,
        include_results: bool,
        coverage_config: Optional["CodeCoverageConfig"],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/test/runs"
        params = {"includeRunDetails": True, **API_PARAMS}
        async for runs in self._get_paginated_by_top_and_skip(url, params=params):
            yield await self._enrich_test_runs(
                runs, project_id, include_results, coverage_config
            )

    async def fetch_test_runs(
        self,
        include_results: bool,
        coverage_config: Optional["CodeCoverageConfig"] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(
            f"Starting to fetch test runs with include_results={include_results}"
        )

        async for projects in self.generate_projects():
            semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_PROJECTS)
            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    functools.partial(
                        self._fetch_enriched_test_runs,
                        project["id"],
                        include_results,
                        coverage_config,
                    ),
                )
                for project in projects
            ]
            async for test_runs in stream_async_iterators_tasks(*tasks):
                yield test_runs

    async def _attach_async_results(
        self,
        runs: list[dict[str, Any]],
        tasks: list[Awaitable[Any]],
        field_name: str,
        default_value: Any,
    ) -> None:
        if not tasks:
            # If no tasks, we will set the default value for every run
            for run in runs:
                run[field_name] = default_value
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for run, value in zip(runs, results):
            if isinstance(value, Exception):
                logger.error(
                    "Error %s occurred while fetching %s for run %s",
                    value,
                    field_name,
                    run.get("id"),
                    exc_info=True,
                )
                continue
            run[field_name] = value

    async def _enrich_test_runs(
        self,
        test_runs: list[dict[str, Any]],
        project_id: str,
        include_results: bool = False,
        coverage_config: Optional["CodeCoverageConfig"] = None,
    ) -> list[dict[str, Any]]:
        logger.info(
            f"Enriching {len(test_runs)} test runs for project {project_id}, include_results={include_results}"
        )

        test_results_tasks: list[Awaitable[list[dict[str, Any]]]] = (
            [self._fetch_test_results(project_id, run["id"]) for run in test_runs]
            if include_results
            else []
        )

        coverage_tasks = self._build_coverage_tasks(
            test_runs, project_id, coverage_config
        )

        await self._attach_async_results(
            test_runs, test_results_tasks, "__testResults", []
        )
        await self._attach_async_results(
            test_runs, coverage_tasks, "__codeCoverage", {}
        )

        return test_runs

    def _build_coverage_tasks(
        self,
        test_runs: list[dict[str, Any]],
        project_id: str,
        coverage_config: Optional["CodeCoverageConfig"],
    ) -> list[Awaitable[dict[str, Any]]]:
        coverage_tasks: list[Awaitable[dict[str, Any]]] = []
        if not coverage_config:
            return coverage_tasks

        skipped_coverage = 0
        for run in test_runs:
            run_id = run.get("id")
            build_id = (run.get("build") or {}).get("id")
            if not build_id:
                skipped_coverage += 1
                logger.debug(
                    f"Skipping code coverage for test run {run_id} in "
                    f"project {project_id}: no associated build"
                )
                coverage_tasks.append(self._no_coverage())
                continue

            coverage_tasks.append(
                self._fetch_code_coverage(project_id, build_id, coverage_config)
            )

        logger.info(
            "Fetched code coverage for {} of {} test runs in project {}. Skipped {} runs without an associated build.",
            len(test_runs) - skipped_coverage,
            len(test_runs),
            project_id,
            skipped_coverage,
        )

        return coverage_tasks

    async def _fetch_test_results(
        self, project_id: str, run_id: str
    ) -> list[dict[str, Any]]:
        """Fetch test results for a specific test run."""
        results = []
        async for page in self._get_paginated_by_top_and_continuation_token(
            f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/test/runs/{run_id}/results"
        ):
            results.extend(page)
        return results

    async def _fetch_code_coverage(
        self, project_id: str, build_id: int, coverage_config: "CodeCoverageConfig"
    ) -> dict[str, Any]:
        logger.info(
            f"Starting to fetch code coverage for project {project_id}, run id={build_id}, flags={coverage_config.flags}"
        )

        params: dict[str, Any] = {"buildId": build_id, **API_PARAMS}
        if coverage_config.flags is not None:
            params["flags"] = coverage_config.flags

        coverage_url = f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/test/codecoverage"
        response = await self.send_request("GET", coverage_url, params=params)
        if not response:
            return {}

        return response.json()

    async def _no_coverage(self) -> dict[str, Any]:
        """Return empty coverage for test runs without a build (e.g., manual test runs)."""
        return {}

    async def get_test_runs_by_build(
        self,
        project_id: str,
        build_id: str,
        include_results: bool = False,
        coverage_config: Optional["CodeCoverageConfig"] = None,
    ) -> list[dict[str, Any]]:
        url = f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/test/runs"
        params: dict[str, Any] = {
            "includeRunDetails": True,
            "buildUri": f"vstfs:///Build/Build/{build_id}",
        }
        all_runs: list[dict[str, Any]] = []
        async for runs in self._get_paginated_by_top_and_skip(url, params=params):
            all_runs.extend(runs)
        if all_runs:
            await self._enrich_test_runs(
                all_runs, project_id, include_results, coverage_config
            )
        return all_runs
