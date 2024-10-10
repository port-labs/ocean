import asyncio
import base64
from typing import Any, Optional, AsyncGenerator, cast

import httpx
from loguru import logger

from integration import (
    SonarQubeIssueResourceConfig,
    CustomSelector,
    SonarQubeProjectResourceConfig,
)
from port_ocean.context.event import event
from port_ocean.utils import http_async_client


class Endpoints:
    PROJECTS = "components/search_projects"
    WEBHOOKS = "webhooks"
    MEASURES = "measures/component"
    BRANCHES = "project_branches/list"
    ONPREM_ISSUES = "issues/list"
    SAAS_ISSUES = "issues/search"
    ANALYSIS = "activity_feed/list"


PAGE_SIZE = 100


class SonarQubeClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        organization_id: str | None,
        app_host: str | None,
        is_onpremise: bool = False,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.organization_id = organization_id
        self.app_host = app_host
        self.is_onpremise = is_onpremise
        self.http_client = http_async_client
        self.http_client.headers.update(self.api_auth_params["headers"])
        self.metrics: list[str] = []

    @property
    def api_auth_params(self) -> dict[str, Any]:
        if self.organization_id:
            return {
                "headers": {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            }

        auth_message = f"{self.api_key}:"
        auth_bytes = auth_message.encode("ascii")
        b64_bytes = base64.b64encode(auth_bytes)
        b64_message = b64_bytes.decode("ascii")
        return {
            "headers": {
                "Authorization": f"Basic {b64_message}",
                "Content-Type": "application/json",
            },
        }

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.debug(
            f"Sending API request to {method} {endpoint} with query params: {query_params}"
        )
        try:
            response = await self.http_client.request(
                method=method,
                url=f"{self.base_url}/api/{endpoint}",
                params=query_params,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def send_paginated_api_request(
        self,
        endpoint: str,
        data_key: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:

        query_params = query_params or {}
        query_params["ps"] = PAGE_SIZE
        all_resources = []  # List to hold all fetched resources

        try:
            logger.debug(
                f"Sending API request to {method} {endpoint} with query params: {query_params}"
            )

            while True:
                response = await self.http_client.request(
                    method=method,
                    url=f"{self.base_url}/api/{endpoint}",
                    params=query_params,
                    json=json_data,
                )
                response.raise_for_status()
                response_json = response.json()
                resource = response_json.get(data_key, [])
                all_resources.extend(resource)

                # Check for paging information and decide whether to fetch more pages
                paging_info = response_json.get("paging")
                if paging_info is None or len(resource) < PAGE_SIZE:
                    break

                query_params["p"] = paging_info["pageIndex"] + 1

            return all_resources

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            if (
                e.response.status_code == 400
                and query_params.get("ps", 0) > PAGE_SIZE
                and endpoint in [Endpoints.ONPREM_ISSUES, Endpoints.SAAS_ISSUES]
            ):
                logger.error(
                    "The request exceeded the maximum number of issues that can be returned (10,000) from SonarQube API. Consider using apiFilters in the config mapping to narrow the scope of your search. Returning accumulated issues and skipping further results."
                )
                return all_resources

            if e.response.status_code == 404:
                logger.error(f"Resource not found: {e.response.text}")
                return all_resources
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching paginated data: {e}")
            raise

    async def get_components(
        self, api_query_params: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve all components from SonarQube organization.

        :return: A list of components associated with the specified organization.
        """
        query_params = {}
        if self.organization_id:
            query_params["organization"] = self.organization_id
            logger.info(
                f"Fetching all components in organization: {self.organization_id}"
            )

        ## Handle api_query_params based on environment
        if not self.is_onpremise:
            logger.warning(
                f"Received request to fetch SonarQube components with api_query_params {api_query_params}. Skipping because api_query_params is only supported on on-premise environments"
            )
        else:
            if api_query_params:
                query_params.update(api_query_params)
            elif event.resource_config:
                # This might be called from places where event.resource_config is not set
                # like on_start() when creating webhooks

                selector = cast(CustomSelector, event.resource_config.selector)
                query_params.update(selector.generate_request_params())

        try:
            response = await self.send_paginated_api_request(
                endpoint=Endpoints.PROJECTS,
                data_key="components",
                query_params=query_params,
            )

            return response
        except Exception as e:
            logger.error(f"Error occurred while fetching components: {e}")
            raise

    async def get_single_component(self, project: dict[str, Any]) -> dict[str, Any]:
        """
        Retrieves a single component from SonarQube organization.

        :param project (dict): A dictionary containing the project information.
        :return: The component details associated with the specified project key.
        """
        project_key = project.get("key")
        logger.info(f"Fetching component data in : {project_key}")
        response = await self.send_api_request(
            endpoint="components/show",
            query_params={"component": project_key},
        )
        return response.get("component", {})

    async def get_measures(self, project_key: str) -> list[Any]:
        """
        Retrieve measures for a specific component from SonarQube API.

        :param project_key: A string containing the project key.

        :return: A list of measures associated with the specified component.
        """
        logger.info(f"Fetching all measures in : {project_key}")
        response = await self.send_api_request(
            endpoint=Endpoints.MEASURES,
            query_params={
                "component": project_key,
                "metricKeys": ",".join(self.metrics),
            },
        )
        return response.get("component", {}).get("measures", [])

    async def get_branches(self, project_key: str) -> list[Any]:
        """A function to make API request to SonarQube and retrieve branches within an organization"""
        logger.info(f"Fetching all branches in : {project_key}")
        response = await self.send_api_request(
            endpoint=Endpoints.BRANCHES, query_params={"project": project_key}
        )
        return response.get("branches", [])

    async def get_single_project(self, project: dict[str, Any]) -> dict[str, Any]:
        """
        Retrieves project information from SonarQube API.

        :param project (dict[str, Any]): A project dictionary containing information about a project.

        :return (list[Any]): A list containing projects data for your organization.
        """
        project_key = cast(str, project.get("key"))
        logger.info(f"Fetching all project information for: {project_key}")

        project["__measures"] = await self.get_measures(project_key)

        branches = await self.get_branches(project_key)
        main_branch = [branch for branch in branches if branch.get("isMain")]
        project["__branch"] = main_branch[0]

        if self.is_onpremise:
            project["__link"] = f"{self.base_url}/dashboard?id={project_key}"
        else:
            project["__link"] = f"{self.base_url}/project/overview?id={project_key}"

        return project

    async def get_all_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve all projects from SonarQube API.

        :return (list[Any]): A list containing projects data for your organization.
        """
        logger.info(f"Fetching all projects in organization: {self.organization_id}")
        self.metrics = cast(
            SonarQubeProjectResourceConfig, event.resource_config
        ).selector.metrics
        components = await self.get_components()
        for component in components:
            project_data = await self.get_single_project(project=component)
            yield [project_data]

    async def get_all_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve issues data across all components from SonarQube API  as an asynchronous generator.

        :return (list[Any]): A list containing issues data for all projects.
        """

        selector = cast(SonarQubeIssueResourceConfig, event.resource_config).selector
        api_query_params = selector.generate_request_params()

        project_api_query_params = (
            selector.project_api_filters.generate_request_params()
            if selector.project_api_filters
            else None
        )

        components = await self.get_components(
            api_query_params=project_api_query_params
        )
        for component in components:
            response = await self.get_issues_by_component(
                component=component, api_query_params=api_query_params
            )
            yield response

    async def get_issues_by_component(
        self,
        component: dict[str, Any],
        api_query_params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve issues data across a single component (in this case, project) from SonarQube API.

        :param components (dict[str, Any]): A component dictionary containing information about a component.

        :return (list[Any]): A list containing issues data for the specified component.
        """
        component_issues = []
        component_key = component.get("key")
        endpoint_path = ""

        if self.is_onpremise:
            query_params = {"project": component_key}
            endpoint_path = Endpoints.ONPREM_ISSUES
        else:
            query_params = {"componentKeys": component_key}
            endpoint_path = Endpoints.SAAS_ISSUES

        if api_query_params:
            query_params.update(api_query_params)

        response = await self.send_paginated_api_request(
            endpoint=endpoint_path,
            data_key="issues",
            query_params=query_params,
        )

        for issue in response:
            issue["__link"] = (
                f"{self.base_url}/project/issues?open={issue.get('key')}&id={component_key}"
            )
            component_issues.append(issue)

        return component_issues

    async def get_all_sonarcloud_analyses(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve analysis data across all components from SonarQube API using asyn generator.

        :return (list[Any]): A list containing analysis data for all components.
        """
        components = await self.get_components()

        for component in components:
            response = await self.get_analysis_by_project(component=component)
            yield response

    async def get_analysis_by_project(
        self, component: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Retrieve analysis data for the given component from SonarQube API.

        :param component (dict[str, Any]): A component dictionary containing information about the component.

        :return (list[dict[str, Any]]): A list containing analysis data for all components.
        """
        component_key = component.get("key")
        component_analysis_data = []

        logger.info(f"Fetching all analysis data in : {component_key}")

        response = await self.send_paginated_api_request(
            endpoint=Endpoints.ANALYSIS,
            data_key="activityFeed",
            query_params={"project": component_key},
        )

        for activity in response:
            if activity["type"] == "analysis":
                analysis_data = activity["data"]
                branch_data = analysis_data.get("branch", {})
                pr_data = analysis_data.get("pullRequest", {})

                analysis_data["__branchName"] = branch_data.get(
                    "name", pr_data.get("branch")
                )
                analysis_data["__analysisDate"] = branch_data.get(
                    "analysisDate", pr_data.get("analysisDate")
                )
                analysis_data["__commit"] = branch_data.get(
                    "commit", pr_data.get("commit")
                )
                analysis_data["__component"] = component
                analysis_data["__project"] = component_key

                component_analysis_data.append(analysis_data)

        return component_analysis_data

    async def get_analysis_for_task(
        self,
        webhook_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Retrieves analysis data associated with a specific task.

        :param webhook_data (dict[str, Any]): A dictionary containing information about the incoming webhook.

        :return (dict[str, Any]): A dictionary containing analysis data for the given project and ID.
        """
        ## Get the compute engine task that runs the analysis
        task_id = webhook_data.get("taskId")
        task_response = await self.send_api_request(
            endpoint="ce/task", query_params={"id": task_id}
        )
        analysis_identifier = task_response.get("task", {}).get("analysisId")

        ## Now get all the analysis data for the given project and and filter by the analysisId
        project = cast(dict[str, Any], webhook_data.get("project"))
        project_analysis_data = await self.get_analysis_by_project(component=project)

        for analysis_object in project_analysis_data:
            if analysis_object.get("analysisId") == analysis_identifier:
                return analysis_object
        return {}  ## when no data is found

    async def get_pull_requests_for_project(
        self, project_key: str
    ) -> list[dict[str, Any]]:
        logger.info(f"Fetching all pull requests in project : {project_key}")
        response = await self.send_api_request(
            endpoint="project_pull_requests/list",
            query_params={"project": project_key},
        )
        return response.get("pullRequests", [])

    async def get_pull_request_measures(
        self, project_key: str, pull_request_key: str
    ) -> list[dict[str, Any]]:
        logger.info(f"Fetching measures for pull request: {pull_request_key}")
        response = await self.send_api_request(
            endpoint=Endpoints.MEASURES,
            query_params={
                "component": project_key,
                "metricKeys": ",".join(self.metrics),
                "pullRequest": pull_request_key,
            },
        )
        return response.get("component", {}).get("measures", [])

    async def enrich_pull_request_with_measures(
        self, project_key: str, pull_request: dict[str, Any]
    ) -> dict[str, Any]:
        pr_measures = await self.get_pull_request_measures(
            project_key, pull_request["key"]
        )
        pull_request["__measures"] = pr_measures
        pull_request["__project"] = project_key
        return pull_request

    async def get_measures_for_all_pull_requests(
        self, project_key: str
    ) -> list[dict[str, Any]]:
        pull_requests = await self.get_pull_requests_for_project(project_key)

        analysis_for_all_pull_requests = await asyncio.gather(
            *[
                self.enrich_pull_request_with_measures(project_key, pr)
                for pr in pull_requests
            ]
        )

        return analysis_for_all_pull_requests

    async def get_all_sonarqube_analyses(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        components = await self.get_components()
        for component in components:
            analysis_data = await self.get_measures_for_all_pull_requests(
                project_key=component["key"]
            )
            yield analysis_data

    def sanity_check(self) -> None:
        try:
            response = httpx.get(f"{self.base_url}/api/system/status", timeout=5)
            response.raise_for_status()
            logger.info("Sonarqube sanity check passed")
            if response.headers.get("content-type") == "application/json":
                logger.info(f"Sonarqube status: {response.json().get('status')}")
                logger.info(f"Sonarqube version: {response.json().get('version')}")
            else:
                logger.info(f"Sonarqube sanity check response: {response.text}")
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Sonarqube failed connectivity check to the sonarqube instance because of HTTP error: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(
                f"Sonarqube failed connectivity check to the sonarqube instance because of HTTP error: {e}"
            )
            raise

    async def get_or_create_webhook_url(self) -> None:
        """
        Get or create webhook URL for projects

        :return: None
        """
        logger.info(f"Subscribing to webhooks in organization: {self.organization_id}")
        webhook_endpoint = Endpoints.WEBHOOKS
        invoke_url = f"{self.app_host}/integration/webhook"
        projects = await self.get_components()

        # Iterate over projects and add webhook
        webhooks_to_create = []
        for project in projects:
            project_key = project["key"]
            logger.info(f"Fetching existing webhooks in project: {project_key}")
            params = {}
            if self.organization_id:
                params["organization"] = self.organization_id
            webhooks_response = await self.send_api_request(
                endpoint=f"{webhook_endpoint}/list",
                query_params={
                    "project": project_key,
                    **params,
                },
            )

            webhooks = webhooks_response.get("webhooks", [])
            logger.info(webhooks)

            if any(webhook["url"] == invoke_url for webhook in webhooks):
                logger.info(f"Webhook already exists in project: {project_key}")
                continue

            params = {}
            if self.organization_id:
                params["organization"] = self.organization_id
            webhooks_to_create.append(
                {
                    "name": "Port Ocean Webhook",
                    "project": project_key,
                    **params,
                }
            )

        for webhook in webhooks_to_create:
            await self.send_api_request(
                endpoint=f"{webhook_endpoint}/create",
                method="POST",
                query_params={**webhook, "url": invoke_url},
            )
            logger.info(f"Webhook added to project: {webhook['project']}")
