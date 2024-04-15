import json
from typing import Any, AsyncGenerator, Optional
from azure_devops.webhooks.webhook_event import WebhookEvent
from httpx import HTTPStatusError
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from loguru import logger
from .base_client import HTTPBaseClient
from port_ocean.utils.cache import cache_iterator_result

API_URL_PREFIX = "_apis"
WEBHOOK_API_PARAMS = {"api-version": "7.1-preview.1"}


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
        params = {"includeCapabilities": "true"}
        projects_url = f"{self._organization_base_url}/{API_URL_PREFIX}/projects"
        async for projects in self._get_paginated_by_top_and_continuation_token(
            projects_url, additional_params=params
        ):
            if sync_default_team:
                logger.info("Adding default team to projects")
                projects = [
                    await self.get_single_project(project["id"]) for project in projects
                ]

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

                if not (include_disabled_repositories):
                    repositories = [
                        repo for repo in repositories if not repo.get("isDisabled")
                    ]

                yield repositories

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
                    "refName": repo["defaultBranch"],
                }
                policies_url = f"{self._organization_base_url}/{repo['project']['id']}/{API_URL_PREFIX}/git/policy/configurations"
                repo_policies = (
                    await self.send_request("GET", policies_url, params=params)
                ).json()["value"]

                for policy in repo_policies:
                    policy["__repository"] = repo
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
