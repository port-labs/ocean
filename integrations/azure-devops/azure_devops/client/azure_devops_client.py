import json
from typing import Any, AsyncGenerator, Optional
from azure_devops.webhooks.webhook_event import WebhookEvent
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from loguru import logger
from .base_client import HTTPBaseClient
from azure_devops.utils import cache_results

API_URL_PREFIX = "_apis"


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

    @cache_results("projects")
    async def generate_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {"includeCapabilities": "true"}
        projects_url = f"{self._organization_base_url}/{API_URL_PREFIX}/projects"
        async for projects in self._get_paginated_by_top_and_continuation_token(
            projects_url, additional_params=params
        ):
            yield projects

    @cache_results("teams")
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
                        member["teamId"] = team["id"]
                    yield members

    @cache_results("repositories")
    async def generate_repositories(self) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                repos_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/git/repositories"
                repositories = self._parse_response_values(
                    await self.send_request("GET", repos_url)
                )
                yield repositories

    async def generate_pull_requests(
        self, search_filters: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for repositories in self.generate_repositories():
            for repository in repositories:
                pull_requests_url = f"{self._organization_base_url}/{repository['project']['id']}/{API_URL_PREFIX}/git/repositories/{repository['id']}/pullrequests"
                async for filtered_pull_requests in self._get_paginated_by_top_and_skip(
                    pull_requests_url, search_filters
                ):
                    yield filtered_pull_requests

    @cache_results("pipelines")
    async def generate_pipelines(self) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                pipelines_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/pipelines"
                async for (
                    pipelines
                ) in self._get_paginated_by_top_and_continuation_token(pipelines_url):
                    for pipeline in pipelines:
                        pipeline["projectId"] = project["id"]
                    yield pipelines

    async def generate_work_items_by_wiql(
        self, wiql_query: str, max_work_items_per_query: int
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        MAX_ALLOWED_ITEMS_IN_BATCH = 200
        data = {"query": wiql_query}
        async for teams in self.generate_teams():
            for team in teams:
                work_items_wiql_params = {
                    "api-version": "6.0",
                    "$top": max_work_items_per_query,
                }
                work_items_wiql_headers = {"Content-Type": "application/json"}
                work_items_wiql_url = f"{self._organization_base_url}/{team['projectId']}/{team['id']}/{API_URL_PREFIX}/wit/wiql"
                wiql_content = (
                    await self.send_request(
                        "POST",
                        work_items_wiql_url,
                        headers=work_items_wiql_headers,
                        params=work_items_wiql_params,
                        data=json.dumps(data),
                    )
                ).json()
                work_items_metadata = wiql_content["workItems"]
                logger.info(
                    f"Found {len(work_items_metadata)} work items in project id {team['projectId']} team name {team['name']} for query: {wiql_query}"
                )
                work_item_ids: list[int] = [
                    work_item_metadata["id"]
                    for work_item_metadata in work_items_metadata
                ]
                for work_item_ids_index in range(
                    0, len(work_item_ids), MAX_ALLOWED_ITEMS_IN_BATCH
                ):
                    work_item_ids_batch = work_item_ids[
                        work_item_ids_index : work_item_ids_index
                        + MAX_ALLOWED_ITEMS_IN_BATCH
                    ]
                    work_items_list_params = {
                        "api-version": "5.1",
                        "ids": ",".join(str(id) for id in work_item_ids_batch),
                    }
                    work_items_list_url = f"{self._organization_base_url}/{team['projectId']}/{API_URL_PREFIX}/wit/workitems"
                    work_items_data = self._parse_response_values(
                        await self.send_request(
                            "GET", work_items_list_url, params=work_items_list_params
                        )
                    )
                    for work_item in work_items_data:
                        work_item["teamId"] = team["id"]
                        work_item["projectId"] = team["projectId"]
                    logger.info(
                        f"Finished proceesing batch of {len(work_items_data)} work items.."
                    )
                    yield work_items_data

    async def generate_boards(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self.generate_projects():
            for project in projects:
                board_list_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/work/boards"
                boards = self._parse_response_values(
                    await self.send_request("GET", board_list_url)
                )
                project_boards: list[dict[Any, Any]] = []
                for board in boards:
                    logger.info(
                        f"Found board {board['name']} in project {project['name']}"
                    )
                    board_data = self._parse_response_values(
                        await self.send_request("GET", board["url"])
                    )
                    project_boards.extend(board_data)
                logger.info(
                    f"Found {len(project_boards)} boards in project {project['name']}"
                )
                yield project_boards

    async def generate_repository_policies(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for repos in self.generate_repositories():
            for repo in repos:
                params = {"repositoryId": repo["id"], "refName": repo["defaultBranch"]}
                policies_url = f"{self._organization_base_url}/{repo['project']['id']}/{API_URL_PREFIX}/git/policy/configurations"
                repo_policies = self._parse_response_values(
                    await self.send_request("GET", policies_url, params=params)
                )
                for policy in repo_policies:
                    policy["repositoryId"] = repo["id"]
                yield repo_policies

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

    async def get_work_item(self, work_item_id: str) -> dict[Any, Any]:
        get_single_pull_reqest_url = f"{self._organization_base_url}/{API_URL_PREFIX}/wit/workitems/{work_item_id}"
        response = await self.send_request("GET", get_single_pull_reqest_url)
        pull_request_data = response.json()
        return pull_request_data

    async def generate_subscriptions_webhook_events(self) -> list[WebhookEvent]:
        headers = {"Content-Type": "application/json"}
        try:
            get_subscriptions_url = (
                f"{self._organization_base_url}/{API_URL_PREFIX}/hooks/subscriptions"
            )
            subscriptions_raw = self._parse_response_values(
                await self.send_request("GET", get_subscriptions_url, headers=headers)
            )
        except json.decoder.JSONDecodeError:
            err_str = "Couldn't decode response from subscritions route. This may be because you are unauthorized- Check PAT (Personal Access Token) validity"
            logger.warning(err_str)
            raise Exception(err_str)
        except Exception as e:
            logger.warning(
                f"Failed to get all existing subscriptions:{type(e)} {str(e)}"
            )
            raise e
        return [WebhookEvent(**subscription) for subscription in subscriptions_raw]

    async def create_subscription(self, webhook_event: WebhookEvent) -> None:
        params = {"api-version": "7.1-preview.1"}
        headers = {"Content-Type": "application/json"}
        create_subscription_url = (
            f"{self._organization_base_url}/{API_URL_PREFIX}/hooks/subscriptions"
        )
        webhook_event_json = webhook_event.json()
        logger.debug(f"Creating subscription to event: {webhook_event_json}")
        response = await self.send_request(
            "POST",
            create_subscription_url,
            params=params,
            headers=headers,
            data=webhook_event_json,
        )
        response_content = response.json()
        logger.info(
            f"Created subscription id: {response_content['id']} for eventType {response_content['eventType']}"
        )

    def _get_item_content(
        self, file_path: str, repository_id: str, versionType: str, version: str
    ) -> bytes:
        items_params = {
            "versionType": versionType,
            "version": version,
            "path": file_path,
        }
        items_url = f"{self._organization_base_url}/{API_URL_PREFIX}/git/repositories/{repository_id}/items"
        try:
            logger.debug(
                f"Getting file {file_path} from repo id {repository_id} by {versionType}: {version}"
            )
            file_content = self.send_sync_get_request(
                items_url, params=items_params
            ).content
        except Exception as e:
            logger.warning(
                f"Couldn't fetch file {file_path} from repo id {repository_id}: {str(e)}"
            )
            return bytes()
        else:
            return file_content

    def get_file_by_branch(
        self, file_path: str, repository_id: str, branch_name: str
    ) -> bytes:
        return self._get_item_content(file_path, repository_id, "Branch", branch_name)

    def get_file_by_commit(
        self, file_path: str, repository_id: str, commit_id: str
    ) -> bytes:
        return self._get_item_content(file_path, repository_id, "Commit", commit_id)
