import asyncio
import functools
import json
from typing import Any, AsyncGenerator, Optional
from httpx import HTTPStatusError
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.utils.cache import cache_iterator_result

from azure_devops.webhooks.webhook_event import WebhookEvent

from .base_client import HTTPBaseClient
from .file_processing import (
    parse_file_content,
)
from port_ocean.utils.async_iterators import (
    stream_async_iterators_tasks,
    semaphore_async_iterator,
)
from port_ocean.utils.queue_utils import process_in_queue


API_URL_PREFIX = "_apis"
WEBHOOK_API_PARAMS = {"api-version": "7.1-preview.1"}
# Maximum number of work item IDs allowed in a single API request
# (based on Azure DevOps API limitations) https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/list?view=azure-devops-rest-7.1&tabs=HTTP
MAX_WORK_ITEMS_PER_REQUEST = 200
MAX_WORK_ITEMS_RESULTS_PER_PROJECT = 19999
MAX_ALLOWED_FILE_SIZE_IN_BYTES = 1 * 1024 * 1024
MAX_CONCURRENT_FILE_DOWNLOADS = 50
MAX_CONCURRENT_REPOS_FOR_FILE_PROCESSING = 25
MAX_CONCURRENT_REPOS_FOR_PULL_REQUESTS = 25


class AzureDevopsClient(HTTPBaseClient):
    def __init__(self, organization_url: str, personal_access_token: str) -> None:
        super().__init__(personal_access_token)
        self._organization_base_url = organization_url

    @classmethod
    def create_from_ocean_config(cls) -> "AzureDevopsClient":
        if cache := event.attributes.get("azure_devops_client"):
            return cache
        azure_devops_client = cls(
            ocean.integration_config["organization_url"].strip("/"),
            ocean.integration_config["personal_access_token"],
        )
        event.attributes["azure_devops_client"] = azure_devops_client
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

    @cache_iterator_result()
    async def generate_projects(
        self, sync_default_team: bool = False
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
                tasks = [self.get_single_project(project["id"]) for project in projects]
                projects_batch: list[dict[str, Any] | None] = await asyncio.gather(
                    *tasks
                )
                projects = [project for project in projects_batch if project]
            yield projects

    @cache_iterator_result()
    async def generate_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
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

        team_tasks = [self.get_team_members(team) for team in teams]

        members_results = await asyncio.gather(*team_tasks)

        total_members = sum(len(members) for members in members_results)
        logger.info(f"Retrieved {total_members} members across {len(teams)} teams")

        for team, members in zip(teams, members_results):
            team["__members"] = members

        return teams

    async def generate_members(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for teams in self.generate_teams():
            for team in teams:
                members = await self.get_team_members(team)
                for member in members:
                    member["__teamId"] = team["id"]
                yield members

    def _format_organization_url_with_subdomain(self, subdomain: str) -> str:
        base_url = self._organization_base_url
        if ".visualstudio.com" in base_url:
            return base_url.replace(
                ".visualstudio.com", f".{subdomain}.visualstudio.com"
            )
        return base_url.replace("dev.azure.com", f"{subdomain}.dev.azure.com")

    async def generate_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        users_url = (
            self._format_organization_url_with_subdomain("vsaex")
            + f"/{API_URL_PREFIX}/userentitlements"
        )
        async for users in self._get_paginated_by_top_and_continuation_token(
            users_url, data_key="items"
        ):
            yield users

    @cache_iterator_result()
    async def generate_repositories(
        self, include_disabled_repositories: bool = True
    ) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                repos_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/git/repositories"
                response = await self.send_request("GET", repos_url)
                if not response:
                    continue
                repositories = response.json()["value"]
                if include_disabled_repositories:
                    yield repositories
                else:
                    yield [
                        repo
                        for repo in repositories
                        if self._repository_is_healthy(repo)
                    ]

    async def generate_pull_requests(
        self, search_filters: Optional[dict[str, Any]] = None
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

    async def generate_releases(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                releases_url = (
                    self._format_organization_url_with_subdomain("vsrm")
                    + f"/{project['id']}/{API_URL_PREFIX}/release/releases"
                )
                async for releases in self._get_paginated_by_top_and_continuation_token(
                    releases_url
                ):
                    yield releases

    async def generate_repository_policies(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for repos in self.generate_repositories(
            include_disabled_repositories=False
        ):
            for repo in repos:
                params = {
                    "repositoryId": repo["id"],
                }
                if default_branch := repo.get("defaultBranch"):
                    params["refName"] = default_branch

                policies_url = f"{self._organization_base_url}/{repo['project']['id']}/{API_URL_PREFIX}/git/policy/configurations"
                response = await self.send_request("GET", policies_url, params=params)
                if not response:
                    continue
                repo_policies = response.json()["value"]

                for policy in repo_policies:
                    policy["__repository"] = repo
                yield repo_policies

    async def generate_work_items(
        self, wiql: Optional[str], expand: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieves a paginated list of work items within the Azure DevOps organization based on a WIQL query.
        """
        async for projects in self.generate_projects():
            for project in projects:
                # Execute WIQL query to get work item IDs
                work_item_ids = await self._fetch_work_item_ids(project, wiql)
                logger.info(
                    f"Found {len(work_item_ids)} work item IDs for project {project['name']}"
                )
                # Fetch work items using the IDs (in batches if needed)
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

    async def _fetch_work_item_ids(
        self, project: dict[str, Any], wiql: Optional[str]
    ) -> list[int]:
        """
        Executes a WIQL query to fetch work item IDs for a given project.

        :param project_id: The ID of the project.
        :return: A list of work item IDs.
        """
        wiql_query = f"SELECT [Id] from WorkItems WHERE [System.TeamProject] = '{project['name']}'"

        if wiql:
            # Append the user-provided wiql to the WHERE clause
            wiql_query += f" AND {wiql}"
            logger.info(f"Found and appended WIQL filter: {wiql}")

        wiql_url = (
            f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/wit/wiql"
        )
        logger.info(
            f"Fetching work item IDs for project {project['name']} using WIQL query {wiql_query}"
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
            return []
        return [item["id"] for item in wiql_response.json()["workItems"]]

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
                f"Processing batch {i//page_size + 1}/{number_of_batches} with {len(batch_ids)} work items for project {project_id}"
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
            yield work_items_response.json()["value"]

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
                get_boards_url = f"{self._organization_base_url}/{project_id}/{team['id']}/{API_URL_PREFIX}/work/boards"
                response = await self.send_request("GET", get_boards_url)
                if not response:
                    continue
                board_data = response.json().get("value", [])
                logger.info(f"Found {len(board_data)} boards for project {project_id}")
                yield await self._enrich_boards(board_data, project_id, team["id"])

    @cache_iterator_result()
    async def get_boards_in_organization(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.generate_projects():
            yield [
                {**board, "__project": project}
                for project in projects
                async for boards in self._get_boards(project["id"])
                for board in boards
            ]

    async def generate_subscriptions_webhook_events(self) -> list[WebhookEvent]:
        headers = {"Content-Type": "application/json"}
        try:
            get_subscriptions_url = (
                f"{self._organization_base_url}/{API_URL_PREFIX}/hooks/subscriptions"
            )
            response = await self.send_request(
                "GET", get_subscriptions_url, headers=headers
            )
            if not response:
                return []
            subscriptions_raw = response.json().get("value", [])
        except json.decoder.JSONDecodeError:
            err_str = "Couldn't decode response from subscritions route. This may be because you are unauthorized- Check PAT (Personal Access Token) validity"
            logger.warning(err_str)
            raise Exception(err_str)
        return [WebhookEvent(**subscription) for subscription in subscriptions_raw]

    async def create_subscription(self, webhook_event: WebhookEvent) -> None:
        headers = {"Content-Type": "application/json"}
        create_subscription_url = (
            f"{self._organization_base_url}/{API_URL_PREFIX}/hooks/subscriptions"
        )
        webhook_event_json = webhook_event.json()
        logger.info(f"Creating subscription to event: {webhook_event_json}")
        response = await self.send_request(
            "POST",
            create_subscription_url,
            params=WEBHOOK_API_PARAMS,
            headers=headers,
            data=webhook_event_json,
        )
        if not response:
            return
        response_content = response.json()
        logger.info(
            f"Created subscription id: {response_content['id']} for eventType {response_content['eventType']}"
        )

    async def delete_subscription(self, webhook_event: WebhookEvent) -> None:
        headers = {"Content-Type": "application/json"}
        delete_subscription_url = f"{self._organization_base_url}/{API_URL_PREFIX}/hooks/subscriptions/{webhook_event.id}"
        logger.info(f"Deleting subscription to event: {webhook_event.json()}")
        await self.send_request(
            "DELETE",
            delete_subscription_url,
            headers=headers,
            params=WEBHOOK_API_PARAMS,
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
                logger.warning("No repositories found. Skipping file discovery.")
                return

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
    ) -> AsyncGenerator[list[dict[str, Any] | None], None]:
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
        project_id = repository["project"]["id"]
        repository_id = repository["id"]

        items_batch_url = f"{self._organization_base_url}/{project_id}/_apis/git/repositories/{repository_id}/itemsbatch"
        logger.debug(f"Items batch URL: {items_batch_url}")

        item_descriptors = [
            {
                "path": path if path.startswith("/") else f"/{path}",
                "recursionLevel": "none",
                "versionDescriptor": {"version": branch, "versionType": "branch"},
            }
            for path in paths
        ]

        request_data = {
            "itemDescriptors": item_descriptors,
            "includeContentMetadata": True,
            "latestProcessedChange": True,
        }

        try:
            response = await self.send_request(
                "POST",
                items_batch_url,
                params={"api-version": "7.1"},
                data=json.dumps(request_data),
                headers={"Content-Type": "application/json"},
            )

            if response is None:
                logger.warning(
                    f"No response from itemsbatch API for repository {repository['name']}"
                )
                return

            if response.status_code == 400:
                logger.warning(
                    f"Bad request (400) for repository {repository['name']}: {response.json().get('message')}"
                )
                return

            batch_results = response.json()

            # Flatten nested arrays to get a single list of file dictionaries
            files = [
                file_info
                for sublist in batch_results.get("value", [])
                for file_info in sublist
            ]
            logger.info(f"Found {len(files)} files in repository {repository['name']}")

            downloaded_files = await process_in_queue(
                files,
                self.download_single_file,
                repository,
                branch,
                concurrency=MAX_CONCURRENT_FILE_DOWNLOADS,
            )

            for file in downloaded_files:
                yield [file]

        except HTTPStatusError as e:
            logger.error(e.response.status_code)
            logger.error(e.response.text)
            if e.response.status_code == 400:
                logger.warning(
                    f"None of the paths {paths} were found in repository {repository['name']}"
                )
            else:
                raise
        except Exception as e:
            logger.error(
                f"Unexpected error processing files in {repository['name']}: {e}"
            )
            raise

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
