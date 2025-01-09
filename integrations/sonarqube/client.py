import asyncio
import base64
from typing import Any, AsyncGenerator, Generator, Optional, cast

import httpx
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.utils.cache import cache_iterator_result


def turn_sequence_to_chunks(
    sequence: list[Any], chunk_size: int
) -> Generator[list[Any], None, None]:
    if chunk_size >= len(sequence):
        yield sequence
        return
    start, end = 0, chunk_size

    while start <= len(sequence) and sequence[start:end]:
        yield sequence[start:end]
        start += chunk_size
        end += chunk_size

    return


MAX_PORTFOLIO_REQUESTS = 20


class Endpoints:
    COMPONENTS = "components/search_projects"
    COMPONENT_SHOW = "components/show"
    PROJECTS = "projects/search"
    WEBHOOKS = "webhooks"
    MEASURES = "measures/component"
    BRANCHES = "project_branches/list"
    ISSUES_SEARCH = "issues/search"
    ANALYSIS = "activity_feed/list"
    PORTFOLIO_DETAILS = "views/show"
    PORTFOLIOS = "views/list"


PAGE_SIZE = 100
PROJECTS_RESYNC_BATCH_SIZE = 20

PORTFOLIO_VIEW_QUALIFIERS = ["VW", "SVW"]


class SonarQubeClient:
    """
    This client has no rate limiting logic implemented. This is
    because [SonarQube API does not have rate limiting)
    [https://community.sonarsource.com/t/need-api-limit-documentation/116582].
    The client is used to interact with the SonarQube API to fetch data.
    """

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
        self.webhook_invoke_url = f"{self.app_host}/integration/webhook"

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

    async def _send_api_request(
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

    async def _send_paginated_request(
        self,
        endpoint: str,
        data_key: str,
        method: str = "GET",
        query_params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        query_params = query_params or {}
        query_params["ps"] = PAGE_SIZE
        logger.info(f"Starting paginated request to {endpoint}")
        try:
            while True:
                response = await self._send_api_request(
                    endpoint=endpoint,
                    method=method,
                    query_params=query_params,
                    json_data=json_data,
                )
                resources = response.get(data_key, [])
                if not resources:
                    logger.warning(f"No {data_key} found in response: {response}")

                if resources:
                    logger.info(f"Fetched {len(resources)} {data_key} from API")
                yield resources

                paging_info = response.get("paging")
                if not paging_info:
                    break

                page_index = paging_info.get(
                    "pageIndex", 1
                )  # SonarQube pageIndex starts at 1
                page_size = paging_info.get("pageSize", PAGE_SIZE)
                total_records = paging_info.get("total", 0)
                logger.error("Fetching paginated data")
                # Check if we have fetched all records
                if page_index * page_size >= total_records:
                    break
                query_params["p"] = page_index + 1
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            if (
                e.response.status_code == 400
                and query_params.get("ps", 0) > PAGE_SIZE
                and endpoint == Endpoints.ISSUES_SEARCH
            ):
                logger.error(
                    "The request exceeded the maximum number of issues that can be returned (10,000) from SonarQube API. Consider using apiFilters in the config mapping to narrow the scope of your search. Returning accumulated issues and skipping further results."
                )

            if e.response.status_code == 404:
                logger.error(f"Resource not found: {e.response.text}")

            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP occurred while fetching paginated data: {e}")
            raise

    @cache_iterator_result()
    async def get_components(
        self,
        query_params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve all components from SonarQube organization.

        :return: A list of components associated with the specified organization.
        """
        if self.organization_id:
            logger.info(
                f"Fetching all components in organization: {self.organization_id}"
            )

        if not self.is_onpremise:
            logger.warning(
                f"Received request to fetch SonarQube components with query_params {query_params}. Skipping because api_query_params is only supported on on-premise environments"
            )

        try:
            async for components in self._send_paginated_request(
                endpoint=Endpoints.COMPONENTS,
                data_key="components",
                method="GET",
                query_params=query_params,
            ):
                logger.info(
                    f"Fetched {len(components)} components {[item.get('key') for item in components]} from SonarQube"
                )
                yield await asyncio.gather(
                    *[self.get_single_project(project) for project in components]
                )
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
        response = await self._send_api_request(
            endpoint=Endpoints.COMPONENT_SHOW,
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
        response = await self._send_api_request(
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
        response = await self._send_api_request(
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
        project["__branches"] = branches
        main_branch = [branch for branch in branches if branch.get("isMain")]
        project["__branch"] = main_branch[0]

        if self.is_onpremise:
            project["__link"] = f"{self.base_url}/dashboard?id={project_key}"
        else:
            project["__link"] = f"{self.base_url}/project/overview?id={project_key}"

        return project

    @cache_iterator_result()
    async def get_projects(
        self, params: dict[str, Any] = {}, enrich_project: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        if self.organization_id:
            params["organization"] = self.organization_id

        async for projects in self._send_paginated_request(
            endpoint=Endpoints.PROJECTS,
            data_key="components",
            method="GET",
            query_params=params,
        ):
            # if enrich_project is True, fetch the project details
            # including measures, branches and link
            if enrich_project:
                yield await asyncio.gather(
                    *[self.get_single_project(project) for project in projects]
                )
            else:
                yield projects

    async def get_all_issues(
        self,
        query_params: dict[str, Any],
        project_query_params: dict[str, Any],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve issues data across all components from SonarQube API  as an asynchronous generator.

        :return (list[Any]): A list containing issues data for all projects.
        """

        async for components in self.get_projects(
            params=project_query_params, enrich_project=False
        ):
            for component in components:
                async for responses in self.get_issues_by_component(
                    component=component, query_params=query_params
                ):
                    yield responses

    async def get_issues_by_component(
        self,
        component: dict[str, Any],
        query_params: dict[str, Any] = {},
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve issues data across a single component (in this case, project) from SonarQube API.

        :param components (dict[str, Any]): A component dictionary containing information about a component.

        :return (list[Any]): A list containing issues data for the specified component.
        """
        component_key = component.get("key")

        if self.is_onpremise:
            query_params["components"] = component_key
        else:
            query_params["componentKeys"] = component_key

        async for responses in self._send_paginated_request(
            endpoint=Endpoints.ISSUES_SEARCH,
            data_key="issues",
            query_params=query_params,
        ):
            yield [
                {
                    **issue,
                    "__link": f"{self.base_url}/project/issues?open={issue.get('key')}&id={component_key}",
                }
                for issue in responses
            ]

    async def get_all_sonarcloud_analyses(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve analysis data across all components from SonarQube API using asyn generator.

        :return (list[Any]): A list containing analysis data for all components.
        """
        async for components in self.get_projects(enrich_project=False):
            tasks = [
                self.get_analysis_by_project(component=component)
                for component in components
            ]
            async for project_analysis in stream_async_iterators_tasks(*tasks):
                yield project_analysis

    async def get_analysis_by_project(
        self, component: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Retrieve analysis data for the given component from SonarQube API.

        :param component (dict[str, Any]): A component dictionary containing information about the component.

        :return (list[dict[str, Any]]): A list containing analysis data for all components.
        """
        component_key = component.get("key")

        logger.info(f"Fetching all analysis data in : {component_key}")

        async for response in self._send_paginated_request(
            endpoint=Endpoints.ANALYSIS,
            data_key="activityFeed",
            query_params={"project": component_key},
        ):
            component_analysis_data = []
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
            yield component_analysis_data

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
        task_response = await self._send_api_request(
            endpoint="ce/task", query_params={"id": task_id}
        )
        analysis_identifier = task_response.get("task", {}).get("analysisId")

        ## Now get all the analysis data for the given project and and filter by the analysisId
        project = cast(dict[str, Any], webhook_data.get("project"))
        async for project_analysis_data in self.get_analysis_by_project(
            component=project
        ):
            for analysis_object in project_analysis_data:
                if analysis_object.get("analysisId") == analysis_identifier:
                    return analysis_object
        return {}  ## when no data is found

    async def get_pull_requests_for_project(
        self, project_key: str
    ) -> list[dict[str, Any]]:
        logger.info(f"Fetching all pull requests in project : {project_key}")
        response = await self._send_api_request(
            endpoint="project_pull_requests/list",
            query_params={"project": project_key},
        )
        return response.get("pullRequests", [])

    async def get_pull_request_measures(
        self, project_key: str, pull_request_key: str
    ) -> list[dict[str, Any]]:
        logger.info(f"Fetching measures for pull request: {pull_request_key}")
        response = await self._send_api_request(
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
        async for components in self.get_projects(enrich_project=False):
            for analysis in await asyncio.gather(
                *[
                    self.get_measures_for_all_pull_requests(
                        project_key=component["key"]
                    )
                    for component in components
                ]
            ):
                yield analysis

    async def _get_all_portfolios(self) -> list[dict[str, Any]]:
        logger.info(
            f"Fetching all root portfolios in organization: {self.organization_id}"
        )
        response = await self._send_api_request(endpoint=Endpoints.PORTFOLIOS)
        return response.get("views", [])

    async def _get_portfolio_details(self, portfolio_key: str) -> dict[str, Any]:
        logger.info(f"Fetching portfolio details for: {portfolio_key}")
        response = await self._send_api_request(
            endpoint=Endpoints.PORTFOLIO_DETAILS,
            query_params={"key": portfolio_key},
        )
        return response

    def _extract_subportfolios(self, portfolio: dict[str, Any]) -> list[dict[str, Any]]:
        logger.info(f"Fetching subportfolios for: {portfolio['key']}")
        subportfolios = portfolio.get("subViews", []) or []
        all_portfolios = []
        for subportfolio in subportfolios:
            if subportfolio.get("qualifier") in PORTFOLIO_VIEW_QUALIFIERS:
                all_portfolios.append(subportfolio)
            all_portfolios.extend(self._extract_subportfolios(subportfolio))
        return all_portfolios

    async def get_all_portfolios(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        if self.organization_id:
            logger.info("Skipping portfolio ingestion since organization ID is absent")
        else:
            logger.info(
                f"Fetching all portfolios in organization: {self.organization_id}"
            )
            portfolios = await self._get_all_portfolios()
            portfolio_keys_chunks = turn_sequence_to_chunks(
                [portfolio["key"] for portfolio in portfolios], MAX_PORTFOLIO_REQUESTS
            )

            for portfolio_keys in portfolio_keys_chunks:
                try:
                    portfolios_data = await asyncio.gather(
                        *[
                            self._get_portfolio_details(portfolio_key)
                            for portfolio_key in portfolio_keys
                        ]
                    )
                    for portfolio_data in portfolios_data:
                        yield [portfolio_data]
                        yield self._extract_subportfolios(portfolio_data)
                except (httpx.HTTPStatusError, httpx.HTTPError) as e:
                    logger.error(
                        f"Error occurred while fetching portfolio details: {e}"
                    )

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

    async def _create_webhook_payload_for_project(
        self, project_key: str
    ) -> dict[str, Any]:
        """
        Create webhook for a project

        :param project_key: Project key

        :return: dict[str, Any]
        """
        logger.info(f"Fetching existing webhooks in project: {project_key}")
        params = {}
        if self.organization_id:
            params["organization"] = self.organization_id

        webhooks_response = await self._send_api_request(
            endpoint=f"{Endpoints.WEBHOOKS}/list",
            query_params={
                "project": project_key,
                **params,
            },
        )

        webhooks = webhooks_response.get("webhooks", [])
        logger.info(webhooks)

        if any(webhook["url"] == self.webhook_invoke_url for webhook in webhooks):
            logger.info(f"Webhook already exists in project: {project_key}")
            return {}

        params = {}
        if self.organization_id:
            params["organization"] = self.organization_id
        return {
            "name": "Port Ocean Webhook",
            "project": project_key,
            **params,
        }

    async def _create_webhooks_for_projects(
        self, webhook_payloads: list[dict[str, Any]]
    ) -> None:
        for webhook in webhook_payloads:
            await self._send_api_request(
                endpoint=f"{Endpoints.WEBHOOKS}/create",
                method="POST",
                query_params={**webhook, "url": self.webhook_invoke_url},
            )
            logger.info(f"Webhook added to project: {webhook['project']}")

    async def get_or_create_webhook_url(self) -> None:
        """
        Get or create webhook URL for projects

        :return: None
        """
        logger.info(f"Subscribing to webhooks in organization: {self.organization_id}")
        async for projects in self.get_projects(enrich_project=False):
            webhooks_to_create = []
            for project in projects:
                project_webhook_payload = (
                    await self._create_webhook_payload_for_project(project["key"])
                )
                if project_webhook_payload:
                    webhooks_to_create.append(project_webhook_payload)

            await self._create_webhooks_for_projects(webhooks_to_create)
