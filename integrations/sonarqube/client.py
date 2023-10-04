from typing import Any, Optional, AsyncGenerator, cast
import httpx
from loguru import logger


class Endpoints:
    PROJECTS = "components/search_projects"
    WEBHOOKS = "webhooks"
    MEASURES = "measures/component"
    BRANCHES = "project_branches/list"
    ISSUES = "issues/search"
    ANALYSIS = "activity_feed/list"


class SonarQubeClient:
    def __init__(
        self, base_url: str, api_key: str, organization_id: str, app_host: str
    ):
        self.base_url = base_url or "https://sonarcloud.io"
        self.api_key = api_key
        self.organization_id = organization_id
        self.app_host = app_host
        self.http_client = httpx.AsyncClient(headers=self.api_auth_header)
        self.metrics = [
            "code_smells",
            "coverage",
            "bugs",
            "vulnerabilities",
            "duplicated_files",
            "security_hotspots",
        ]

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        try:
            response = await self.http_client.request(
                method=method,
                url=f"{self.base_url}/api/{endpoint}",
                params=query_params,
                json=json_data,
                headers=self.api_auth_header,
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
        try:
            all_resources = []  # List to hold all fetched resources

            while True:
                response = await self.http_client.request(
                    method=method,
                    url=f"{self.base_url}/api/{endpoint}",
                    params=query_params,
                    json=json_data,
                    headers=self.api_auth_header,
                )
                response.raise_for_status()
                response_json = response.json()

                all_resources.extend(response_json.get(data_key, []))

                # Check for paging information and decide whether to fetch more pages
                paging_info = response_json.get("paging")
                if paging_info and paging_info.get("pageIndex", 0) * paging_info.get(
                    "pageSize", 0
                ) < paging_info.get("total", 0):
                    query_params = query_params or {}
                    query_params["p"] = paging_info["pageIndex"] + 1
                else:
                    break

            return all_resources

        except httpx.HTTPStatusError as e:
            print(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def get_components(self) -> list[Any]:
        """
        Retrieve all components from SonarQube organization.

        :return: A list of components associated with the specified organization.
        """
        logger.info(f"Fetching all components in organization: {self.organization_id}")
        response = await self.send_paginated_api_request(
            endpoint=Endpoints.PROJECTS,
            data_key="components",
            query_params={"organization": self.organization_id},
        )
        return response

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
        project["__link"] = f"{self.base_url}/project/overview?id={project_key}"

        return project

    async def get_all_projects(self) -> list[dict[str, Any]]:
        """
        Retrieve all projects from SonarQube API.

        :return (list[Any]): A list containing projects data for your organization.
        """
        logger.info(f"Fetching all projects in organization: {self.organization_id}")
        components = await self.get_components()
        all_projects = []
        for component in components:
            project_data = await self.get_single_project(project=component)
            all_projects.append(project_data)
        return all_projects

    async def get_all_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve issues data across all components from SonarQube API  as an asynchronous generator.

        :return (list[Any]): A list containing issues data for all projects.
        """
        components = await self.get_components()

        for component in components:
            response = await self.get_issues_by_component(component=component)
            yield response

    async def get_issues_by_component(
        self, component: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Retrieve issues data across a single component (in this case, project) from SonarQube API.

        :param components (dict[str, Any]): A component dictionary containing information about a component.

        :return (list[Any]): A list containing issues data for the specified component.
        """
        component_issues = []
        component_key = component.get("key")
        logger.info(f"Fetching all issues in component: {component_key}")
        response = await self.send_paginated_api_request(
            endpoint=Endpoints.ISSUES,
            data_key="issues",
            query_params={"componentKeys": component_key},
        )

        for issue in response:
            issue[
                "__link"
            ] = f"{self.base_url}/project/issues?open={issue.get('key')}&id={component_key}"
            component_issues.append(issue)

        return component_issues

    async def get_all_analyses(self) -> AsyncGenerator[list[dict[str, Any]], None]:
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
            webhooks_response = await self.send_api_request(
                endpoint=f"{webhook_endpoint}/list",
                query_params={
                    "project": project_key,
                    "organization": self.organization_id,
                },
            )

            webhooks = webhooks_response.get("webhooks", [])
            logger.info(webhooks)

            if any(webhook["url"] == invoke_url for webhook in webhooks):
                logger.info(f"Webhook already exists in project: {project_key}")
                continue
            webhooks_to_create.append(
                {
                    "name": "Port Ocean Webhook",
                    "project": project_key,
                    "organization": self.organization_id,
                }
            )

        for webhook in webhooks_to_create:
            await self.send_api_request(
                endpoint=f"{webhook_endpoint}/create",
                method="POST",
                query_params={**webhook, "url": invoke_url},
            )
            logger.info(f"Webhook added to project: {webhook['project']}")
