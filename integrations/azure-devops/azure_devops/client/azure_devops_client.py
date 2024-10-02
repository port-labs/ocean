import json
import asyncio
import typing

from typing import Any, AsyncGenerator, Optional
from httpx import HTTPStatusError
from loguru import logger

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.utils.cache import cache_iterator_result

from azure_devops.misc import AzureDevopsWorkItemResourceConfig
from azure_devops.webhooks.webhook_event import WebhookEvent

from .base_client import HTTPBaseClient


API_URL_PREFIX = "_apis"
WEBHOOK_API_PARAMS = {"api-version": "7.1-preview.1"}
# Maximum number of work item IDs allowed in a single API request
# (based on Azure DevOps API limitations) https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/list?view=azure-devops-rest-7.1&tabs=HTTP
MAX_WORK_ITEMS_PER_REQUEST = 200
MAX_WORK_ITEMS_RESULTS_PER_PROJECT = 20000


class AzureDevopsClient(HTTPBaseClient):
    def __init__(self, organization_url: str, personal_access_token: str) -> None:
        super().__init__(personal_access_token)
        self._organization_base_url = organization_url

    @classmethod
    def create_from_ocean_config(cls) -> "AzureDevopsClient":
        if cache := event.attributes.get("azure_devops_client"):
            return cache
        azure_devops_client = cls(
            ocean.integration_config["organization_url"],
            ocean.integration_config["personal_access_token"],
        )
        event.attributes["azure_devops_client"] = azure_devops_client
        return azure_devops_client

    async def get_single_project(self, project_id: str) -> dict[str, Any]:
        project_url = (
            f"{self._organization_base_url}/{API_URL_PREFIX}/projects/{project_id}"
        )
        project = (await self.send_request("GET", project_url)).json()
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
                projects = await asyncio.gather(*tasks)
            yield projects

    @cache_iterator_result()
    async def generate_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        teams_url = f"{self._organization_base_url}/{API_URL_PREFIX}/teams"
        async for teams in self._get_paginated_by_top_and_skip(teams_url):
            yield teams

    async def generate_members(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for teams in self.generate_teams():
            for team in teams:
                members_in_teams_url = f"{self._organization_base_url}/{API_URL_PREFIX}/projects/{team['projectId']}/teams/{team['id']}/members"
                async for members in self._get_paginated_by_top_and_skip(
                    members_in_teams_url
                ):
                    for member in members:
                        member["__teamId"] = team["id"]
                    yield members

    @cache_iterator_result()
    async def generate_repositories(
        self, include_disabled_repositories: bool = True
    ) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                repos_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/git/repositories"
                repositories = (await self.send_request("GET", repos_url)).json()[
                    "value"
                ]
                if include_disabled_repositories:
                    yield repositories
                else:
                    yield [repo for repo in repositories if not repo.get("isDisabled")]

    async def generate_pull_requests(
        self, search_filters: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for repositories in self.generate_repositories(
            include_disabled_repositories=False
        ):
            for repository in repositories:
                pull_requests_url = f"{self._organization_base_url}/{repository['project']['id']}/{API_URL_PREFIX}/git/repositories/{repository['id']}/pullrequests"
                async for filtered_pull_requests in self._get_paginated_by_top_and_skip(
                    pull_requests_url, search_filters
                ):
                    yield filtered_pull_requests

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
                repo_policies = (
                    await self.send_request("GET", policies_url, params=params)
                ).json()["value"]

                for policy in repo_policies:
                    policy["__repository"] = repo
                yield repo_policies

    async def generate_work_items(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieves a paginated list of work items within the Azure DevOps organization based on a WIQL query.
        """
        async for projects in self.generate_projects():
            for project in projects:
                # 1. Execute WIQL query to get work item IDs
                work_item_ids = await self._fetch_work_item_ids(project)
                logger.info(
                    f"Found {len(work_item_ids)} work item IDs for project {project['name']}"
                )
                # 2. Fetch work items using the IDs (in batches if needed)
                work_items = await self._fetch_work_items_in_batches(
                    project["id"], work_item_ids
                )
                logger.debug(f"Received {len(work_items)} work items")

                # Call the private method to add __projectId to each work item
                work_items = self._add_project_details_to_work_items(
                    work_items, project
                )
                yield work_items

    async def _fetch_work_item_ids(self, project: dict[str, Any]) -> list[int]:
        """
        Executes a WIQL query to fetch work item IDs for a given project.

        :param project_id: The ID of the project.
        :return: A list of work item IDs.
        """
        config = typing.cast(AzureDevopsWorkItemResourceConfig, event.resource_config)
        wiql_query = (
            f"SELECT [Id] from WorkItems WHERE [System.AreaPath] = '{project['name']}'"
        )

        if config.selector.wiql:
            # Append the user-provided wiql to the WHERE clause
            wiql_query += f" AND {config.selector.wiql}"
            logger.info(f"Found and appended WIQL filter: {config.selector.wiql}")

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
        wiql_response.raise_for_status()
        return [item["id"] for item in wiql_response.json()["workItems"]]

    async def _fetch_work_items_in_batches(
        self, project_id: str, work_item_ids: list[int]
    ) -> list[dict[str, Any]]:
        """
        Fetches work items in batches based on the list of work item IDs.

        :param project_id: The ID of the project.
        :param work_item_ids: A list of work item IDs to fetch.
        :return: A list of work items.
        """
        work_items = []
        for i in range(0, len(work_item_ids), MAX_WORK_ITEMS_PER_REQUEST):
            batch_ids = work_item_ids[i : i + MAX_WORK_ITEMS_PER_REQUEST]
            work_items_url = f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/wit/workitems"
            params = {
                "ids": ",".join(map(str, batch_ids)),
                "api-version": "7.1-preview.3",
            }
            work_items_response = await self.send_request(
                "GET", work_items_url, params=params
            )
            work_items_response.raise_for_status()
            work_items.extend(work_items_response.json()["value"])

        return work_items

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

    async def get_pull_request(self, pull_request_id: str) -> dict[Any, Any]:
        get_single_pull_request_url = f"{self._organization_base_url}/{API_URL_PREFIX}/git/pullrequests/{pull_request_id}"
        response = await self.send_request("GET", get_single_pull_request_url)
        pull_request_data = response.json()
        return pull_request_data

    async def get_repository(self, repository_id: str) -> dict[Any, Any]:
        get_single_repository_url = f"{self._organization_base_url}/{API_URL_PREFIX}/git/repositories/{repository_id}"
        response = await self.send_request("GET", get_single_repository_url)
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
        self, boards: list[dict[str, Any]], project_id: str
    ) -> list[dict[str, Any]]:
        for board in boards:
            response = await self.send_request(
                "GET",
                f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/work/boards/{board['id']}",
            )
            board.update(response.json())
        return boards

    async def _get_boards(self, project_id: str) -> list[dict[str, Any]]:
        get_boards_url = (
            f"{self._organization_base_url}/{project_id}/{API_URL_PREFIX}/work/boards"
        )
        response = await self.send_request("GET", get_boards_url)
        board_data = response.json().get("value", [])
        logger.info(f"Found {len(board_data)} boards for project {project_id}")
        return await self._enrich_boards(board_data, project_id)

    @cache_iterator_result()
    async def get_boards_in_organization(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.generate_projects():
            yield [
                {**board, "__project": project}
                for project in projects
                for board in await self._get_boards(project["id"])
            ]

    async def generate_subscriptions_webhook_events(self) -> list[WebhookEvent]:
        headers = {"Content-Type": "application/json"}
        try:
            get_subscriptions_url = (
                f"{self._organization_base_url}/{API_URL_PREFIX}/hooks/subscriptions"
            )
            subscriptions_raw = (
                await self.send_request("GET", get_subscriptions_url, headers=headers)
            ).json()["value"]
        except json.decoder.JSONDecodeError:
            err_str = "Couldn't decode response from subscritions route. This may be because you are unauthorized- Check PAT (Personal Access Token) validity"
            logger.warning(err_str)
            raise Exception(err_str)
        except Exception as e:
            logger.warning(
                f"Failed to get all existing subscriptions:{type(e)} {str(e)}"
            )
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
            file_content = (
                await self.send_request(
                    method="GET", url=items_url, params=items_params
                )
            ).content
        except HTTPStatusError as e:
            general_err_msg = f"Couldn't fetch file {file_path} from repo id {repository_id}: {str(e)}. Returning empty file."
            if e.response.status_code == 404:
                logger.warning(
                    f"{general_err_msg} This may be because the repo {repository_id} is disabled."
                )
            else:
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
