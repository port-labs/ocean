import asyncio
import json
from typing import Any, AsyncGenerator, Optional
from azure_devops.webhooks.webhook_event import WebhookEvent
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from loguru import logger
from .base_client import HTTPBaseClient
from port_ocean.utils.cache import cache_iterator_result

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

    @cache_iterator_result("projects")
    async def generate_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {"includeCapabilities": "true"}
        projects_url = f"{self._organization_base_url}/{API_URL_PREFIX}/projects"
        async for projects in self._get_paginated_by_top_and_continuation_token(
            projects_url, additional_params=params
        ):
            yield projects

    @cache_iterator_result("teams")
    async def generate_teams(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        teams_url = f"{self._organization_base_url}/{API_URL_PREFIX}/teams"
        async for teams in self._get_paginated_by_top_and_skip(teams_url):
            yield teams

    async def generate_members(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async def _get_members_in_team(
            team: dict[str, Any]
        ) -> list[dict[str, Any]]:
            members_in_teams_url = f"{self._organization_base_url}/{API_URL_PREFIX}/projects/{team['projectId']}/teams/{team['id']}/members"
            return self._get_paginated_by_top_and_skip(members_in_teams_url)

        async for teams in self.generate_teams():
            member_tasks = []
            for team in teams:
                member_tasks.append(
                    _get_members_in_team(team)
                )

            for coro in asyncio.as_completed(member_tasks):
                members = await coro
                for member in members:
                    member["teamId"] = team["id"]
                yield members


    async def generate_repositories(self) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async for projects in self.generate_projects():
            repo_tasks = []
            for project in projects:
                repos_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/git/repositories"
                repo_tasks.append(
                    self.send_request("GET", repos_url)
                )

            for future in asyncio.as_completed(repo_tasks):
                response = await future
                repositories = response.json()["value"]
                yield repositories


    async def generate_pull_requests(self, search_filters: Optional[dict[str, Any]] = None) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async def _get_pull_requests(url: str, search_filters: Optional[dict[str, Any]]) -> list[dict[Any, Any]]:
            pull_requests = []
            async for page in self._get_paginated_by_top_and_skip(url, search_filters):
                pull_requests.extend(page)
            return pull_requests
        
        async for repositories in self.generate_repositories():
            pull_request_tasks = []
            for repository in repositories:
                pull_requests_url = f"{self._organization_base_url}/{repository['project']['id']}/{API_URL_PREFIX}/git/repositories/{repository['id']}/pullrequests"
                pull_request_tasks.append(
                    _get_pull_requests(pull_requests_url, search_filters)
                )

            for coro in asyncio.as_completed(pull_request_tasks):
                filtered_pull_requests = await coro
                yield filtered_pull_requests

    async def generate_pipelines(self) -> AsyncGenerator[list[dict[Any, Any]], None]:
        async def _get_pipelines(url: str) -> list[dict[Any, Any]]:
            pipelines = []
            async for page in self._get_paginated_by_top_and_skip(url):
                pipelines.extend(page)
            return pipelines

        async for projects in self.generate_projects():
            pipeline_tasks = []
            for project in projects:
                pipelines_url = f"{self._organization_base_url}/{project['id']}/{API_URL_PREFIX}/pipelines"
                pipeline_tasks.append(
                    _get_pipelines(pipelines_url)
                )

            for coro in asyncio.as_completed(pipeline_tasks):
                pipelines = await coro
                for pipeline in pipelines:
                    pipeline["projectId"] = project["id"]
                yield pipelines

    async def generate_repository_policies(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for repos in self.generate_repositories():
            policy_tasks = []
            for repo in repos:
                params = {"repositoryId": repo["id"], "refName": repo["defaultBranch"]}
                policies_url = f"{self._organization_base_url}/{repo['project']['id']}/{API_URL_PREFIX}/git/policy/configurations"
                policy_tasks.append(
                    self.send_request("GET", policies_url, params=params)
                )

            for coro in asyncio.as_completed(policy_tasks):
                response = await coro
                repo_policies = response.json()["value"]
                for policy in repo_policies:
                    policy["__repositoryId"] = repo["id"]
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
        params = {"api-version": "7.1-preview.1"}
        headers = {"Content-Type": "application/json"}
        create_subscription_url = (
            f"{self._organization_base_url}/{API_URL_PREFIX}/hooks/subscriptions"
        )
        webhook_event_json = webhook_event.json()
        logger.info(f"Creating subscription to event: {webhook_event_json}")
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
            file_content = (await self.send_request(method="GET", url=items_url, params=items_params)).content

        except Exception as e:
            logger.warning(
                f"Couldn't fetch file {file_path} from repo id {repository_id}: {str(e)}"
            )
            return bytes()
        else:
            return file_content

    async def get_file_by_branch(
        self, file_path: str, repository_id: str, branch_name: str
    ) -> bytes:
        return self._get_item_content(file_path, repository_id, "Branch", branch_name)

    async def get_file_by_commit(
        self, file_path: str, repository_id: str, commit_id: str
    ) -> bytes:
        return self._get_item_content(file_path, repository_id, "Commit", commit_id)
