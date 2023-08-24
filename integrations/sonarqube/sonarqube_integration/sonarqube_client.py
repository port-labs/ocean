from typing import Any, Optional
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
        self,
        base_url: str,
        api_key: str,
        organization_id: str,
        app_host: str,
        http_client: httpx.AsyncClient,
    ):
        """
        Initialize SonarQubeClient

        :param base_url: SonarQube base URL
        :param api_key: SonarQube API key
        :param organization_id: SonarQube organization ID
        :param app_host: Application host URL
        :param http_client: httpx.AsyncClient instance
        """
        self.base_url = base_url
        self.api_key = api_key
        self.organization_id = organization_id
        self.app_host = app_host
        self.http_client = http_client
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
        """
        Sends an API request to SonarQube

        :param endpoint: API endpoint URL
        :param method: HTTP method (default: 'GET')
        :param query_params: Query parameters (default: None)
        :param json_data: JSON data to send in request body (default: None)
        :return: Response JSON data
        """
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
        """
        Sends an API request to SonarQube

        :param endpoint: API endpoint URL
        :param data_key: Resource key to fetch
        :param method: HTTP method (default: 'GET')
        :param query_params: Query parameters (default: None)
        :param json_data: JSON data to send in request body (default: None)
        :return: Response JSON data
        """
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

    async def get_measures(self, component: dict[str, Any]) -> list[Any]:
        """
        Retrieve measures for a specific component from SonarQube API.

        :param component: A dictionary containing information about the component.

        :return: A list of measures associated with the specified component.
        """
        logger.info(f"Fetching all measures in : {component.get('key')}")
        response = await self.send_api_request(
            endpoint=Endpoints.MEASURES,
            query_params={
                "component": component.get("key"),
                "metricKeys": ",".join(self.metrics),
            },
        )
        return response.get("component", {}).get("measures", [])

    async def get_branches(self, component: dict[str, Any]) -> list[Any]:
        """A function to make API request to SonarQube and retrieve measures within an organization"""
        logger.info(f"Fetching all branches in : {component.get('key')}")
        response = await self.send_api_request(
            endpoint=Endpoints.BRANCHES, query_params={"project": component.get("key")}
        )
        return response.get("branches", [])

    async def get_projects(self) -> list[Any]:
        """
        Retrieve all projects from SonarQube API.

        :return (list[Any]): A list containing projects data for your organization.
        """
        logger.info(f"Fetching all projects in organization: {self.organization_id}")
        components = await self.get_components()
        all_projects = []
        for component in components:
            component["measures"] = await self.get_measures(component)

            branches = await self.get_branches(component)
            main_branch = [branch for branch in branches if branch.get("isMain")]
            component["branch"] = main_branch[0]
            component[
                "link"
            ] = f"{self.base_url}/project/overview?id={component.get('key')}"

            all_projects.append(component)

        return all_projects

    async def get_issues(
        self, components: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Retrieve issues data across all components from SonarQube API.

        :param components (list[dict[str, Any]]): A list of component dictionaries, each containing information about a component.

        :return (list[Any]): A list containing issues data for all components.
        """
        all_issues = []

        for component in components:
            logger.info(f"Fetching all issues in component: {component.get('key')}")
            response = await self.send_paginated_api_request(
                endpoint=Endpoints.ISSUES,
                data_key="issues",
                query_params={"componentKeys": component.get("key")},
            )

            component_issues = []
            for issue in response:
                issue[
                    "link"
                ] = f"{self.base_url}/project/issues?open={issue.get('key')}&id={component.get('key')}"
                component_issues.append(issue)

            all_issues.extend(component_issues)

        return all_issues

    async def get_analyses(self, components: list[dict[str, Any]]) -> list[Any]:
        """
        Retrieve analysis data across all components from SonarQube API.

        :param components (list[dict[str, Any]]): A list of component dictionaries, each containing information about a component.

        :return (list[Any]): A list containing analysis data for all components.
        """
        all_analysis = []
        for component in components:
            logger.info(f"Fetching all analysis in : {component.get('key')}")
            response = await self.send_paginated_api_request(
                endpoint=Endpoints.ANALYSIS,
                data_key="activityFeed",
                query_params={"project": component.get("key")},
            )
            component_analysis = []

            for activity in response:
                if activity["type"] == "analysis":
                    analysis_data = activity["data"]
                    branch_data = analysis_data.get("branch", {})
                    pr_data = analysis_data.get("pullRequest", {})

                    analysis_data["branch_name"] = branch_data.get(
                        "name", pr_data.get("branch")
                    )
                    analysis_data["analysis_date"] = branch_data.get(
                        "analysisDate", pr_data.get("analysisDate")
                    )
                    analysis_data["commit"] = branch_data.get(
                        "commit", pr_data.get("commit")
                    )

                    analysis_data["project"] = component.get("key")

                    component_analysis.append(analysis_data)

            all_analysis.extend(component_analysis)

        return all_analysis

    async def get_or_create_webhook_url(self) -> None:
        """
        Get or create webhook URL for projects

        :return: None
        """
        logger.info(f"Subscribing to webhooks in organization: {self.organization_id}")
        webhook_endpoint = Endpoints.WEBHOOKS
        invoke_url = f"{self.app_host}/integration/webhook"
        projects = await self.get_projects()

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
