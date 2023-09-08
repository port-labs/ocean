from typing import Any, Optional, AsyncGenerator
import httpx
from loguru import logger
from datetime import datetime

PAGE_SIZE = 50

endpoint_resource_type_mapper = {
    "environment": "environments",
    "service": "services",
    "incident": "incidents",
    "retrospective": "post_mortems/reports",
}


class FirehydrantClient:
    def __init__(self, base_url: str, api_key: str, app_host: str):
        """
        Initialize Firehydrant client

        :param base_url: SonarQube base URL
        :param api_key: SonarQube API key
        :param organization_id: SonarQube organization ID
        :param app_host: Application host URL
        :param http_client: httpx.AsyncClient instance
        """
        self.base_url = base_url
        self.api_key = api_key
        self.app_host = app_host
        self.http_client = httpx.AsyncClient(headers=self.api_auth_header)

    @property
    def api_auth_header(self) -> dict[str, Any]:
        return {
            "Authorization": f"{self.api_key}",
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
                url=f"{self.base_url}/v1/{endpoint}",
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
                    url=f"{self.base_url}/v1/{endpoint}",
                    params=query_params,
                    json=json_data,
                    headers=self.api_auth_header,
                )
                response.raise_for_status()
                response_json = response.json()

                all_resources.extend(response_json.get(data_key, []))

                # Check for paging information and decide whether to fetch more pages
                paging_info = response_json.get("pagination")
                if paging_info and paging_info.get("page", 0) < paging_info.get(
                    "pages", 0
                ):
                    query_params = query_params or {}
                    query_params["page"] = paging_info["page"] + 1
                else:
                    break

            return all_resources

        except httpx.HTTPStatusError as e:
            print(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise

    async def get_paginated_resource(
        self, resource_type: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch paginated resources of a specific type from the Firehydrant API.

        Args:
            resource_type (str): The type of resource to fetch, e.g., "incidents" or "webhooks."

        Yields:
            AsyncGenerator[list[dict[str, Any]], None]: A generator that yields lists of resource data.
                Each yielded list contains a batch of resources of the specified type.

        Returns:
            None: This function does not return a value but yields resource data via asynchronous iteration.
        """
        logger.info(f"Getting {resource_type} from Firehydrant")
        endpoint = endpoint_resource_type_mapper.get(resource_type, "")

        pagination_params: dict[str, Any] = {
            "page": 1,
            "per_page": PAGE_SIZE,
        }

        try:
            while True:
                response = await self.send_api_request(
                    endpoint=endpoint, query_params=pagination_params
                )
                if response.get("data"):
                    yield response["data"]
                else:
                    logger.warning(f"No {resource_type} found in the response")

                pagination_params["page"] += 1

                if pagination_params["page"] > response.get("pagination", {}).get(
                    "pages"
                ):
                    break

        except Exception as e:
            logger.error(f"Error while fetching {resource_type}: {str(e)}")

    async def enrich_incident_report_data(
        self, report: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Enriches an incident report by adding tasks, duration, and retrospective questions. It takes an incident report as input and adds additional information to it, including tasks related to the incident, duration metrics, and retrospective questions. The resulting enriched report is returned as a dictionary.

        Args:
            report (dict[str, Any]): The incident report data to be enriched.

        Returns:
            dict[str, Any]: The enriched incident report with added information.
        """

        ## get incident task completion summary statistics
        incident_id = report.get("incident", {}).get("id")
        task_completion_status = await self.get_tasks_by_incident(
            incident_id=incident_id
        )

        ## get incident duration data
        milestones = report.get("incident", {}).get("milestones", [])
        incident_duration = await self.compute_incident_duration(milestones=milestones)

        ## get retrospective questions and answers
        retro_responses = await self.get_retrospective_questions_and_answers(
            questions=report.get("questions", [])
        )

        return {
            "tasks": task_completion_status,
            "duration": incident_duration,
            "questions": retro_responses,
        }

    async def get_tasks_by_incident(self, incident_id: str) -> dict[str, Any]:
        """
        Retrieve tasks associated with a specific incident. The returned data includes details about each task, such as the number of completed and incompleted tasks.

        Args:
            incident_id (str): The unique identifier of the incident for which to fetch tasks.

        Returns:
            dict[str, Any]: A dictionary containing information about tasks related to the incident.
        """
        logger.info(f"Getting tasks details for incident: {incident_id}")
        params: dict[str, Any] = {
            "page": 1,
            "per_page": PAGE_SIZE,
        }
        task_url = f"incidents/{incident_id}/tasks"

        tasks = await self.send_paginated_api_request(
            endpoint=task_url, query_params=params, data_key="data"
        )
        task_completion_status = await self.get_task_completion_status(tasks)
        return task_completion_status

    async def get_task_completion_status(
        self, tasks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Return statistics about completed and uncompleted tasks. It returns a dictionary with counts of completed and uncompleted tasks, providing insights into task progress.

        Args:
            tasks (list[dict[str, Any]]): A list of task objects, each represented as a dictionary.

        Returns:
            dict[str, Any]: A dictionary containing statistics about completed and uncompleted tasks.
        """
        logger.info("Computing task completion statistics")
        total_completed_tasks = 0
        for task in tasks:
            if task.get("state") == "done":
                total_completed_tasks += 1

        return {
            "completed": total_completed_tasks,
            "incompleted": len(tasks) - total_completed_tasks,
        }

    async def compute_incident_duration(
        self, milestones: list[dict[str, Any]]
    ) -> Optional[float]:
        """Compute the duration in minutes it took to resolve an incident based on milestones.

        Args:
            milestones (list[dict[str, Any]]): A list of milestone objects representing incident events.

        Returns:
            float: The duration in minutes it took to resolve the incident.
        """
        started_time = None
        resolved_time = None

        # Iterate through the milestones to find the "started" and "resolved" events.
        for milestone in milestones:
            event_type = milestone.get("type")
            occurred_at = milestone.get("occurred_at", "")

            # Check if the event is a "started" event.
            if event_type == "started":
                started_time = datetime.fromisoformat(occurred_at[:-1])

            # Check if the event is a "resolved" event.
            if event_type == "resolved":
                resolved_time = datetime.fromisoformat(occurred_at[:-1])

        # Calculate the duration if both "started" and "resolved" events are found.
        if started_time and resolved_time:
            duration = resolved_time - started_time
            duration_hours = duration.total_seconds() / 60  # Convert to minutes
            return round(duration_hours, 2)

        return None  # Return None if either "started" or "resolved" event is missing.

    async def get_retrospective_questions_and_answers(
        self, questions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Format retrospective questions by renaming title to 'question' and body to 'answer'.

        Args:
            questions (list[dict[str, Any]]): A list of retrospective question objects.

        Returns:
            list[dict[str, Any]]: A list of formatted retrospective questions with 'question' and 'answer' keys.
        """

        retro_responses_list = []
        for question in questions:
            retro_responses_list.append(
                {"question": question.get("title"), "answer": question.get("body")}
            )
        return retro_responses_list

    async def compute_service_mean_time_metrics(
        self, active_incidents_ids: list[Any]
    ) -> dict[str, Any]:
        """Computes mean time service details for active incidents.

        Args:
            active_incidents_ids (list[Any]): A list of active incident IDs.

        Returns:
            dict[str, Any]: A dictionary containing computed mean time service metrics,
            including time to acknowledge, time to identify, time to mitigate, and time to resolve.

        Note:
            This function calculates various incident analytics metrics based on milestone data.
            The metrics may include Mean Time to Detection (MTTD), Mean Time to Acknowledged (MTTA),
            Mean Time to Mitigation (MTTM), and Mean Time to Resolution (MTTR).
        """

        if len(active_incidents_ids) == 0:
            return {}

        service_metrics = {
            "time_to_acknowledge": 0,
            "time_to_identify": 0,
            "time_to_mitigate": 0,
            "time_to_resolve": 0,
        }

        for incident_id in active_incidents_ids:
            incident_data = await self.get_single_incident(incident_id=incident_id)
            milestones = incident_data.get("milestones", {})
            incident_metrics = await self.compute_incident_analytics_metrics(
                milestones=milestones
            )

            # Update the cumulative metrics for the service
            for metric_name, metric_value in incident_metrics.items():
                service_metrics[metric_name] += metric_value

        # Calculate the average metrics for the service
        for metric_name in service_metrics:
            service_metrics[metric_name] //= len(active_incidents_ids)

        return service_metrics

    async def get_single_incident(self, incident_id: str) -> dict[str, Any]:
        """Retrieve information about a single incident by its unique identifier.

        Args:
            incident_id (str): The unique identifier of the incident to retrieve.

        Returns:
            dict[str, Any]: A dictionary containing information about the specified incident.

        """
        return await self.send_api_request(endpoint=f"incidents/{incident_id}")

    async def compute_incident_analytics_metrics(
        self, milestones: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Compute incident analytics metrics based on milestone data. Formular retrieved from https://firehydrant.com/docs/managing-incidents/incident-metrics/

        Args:
            milestones (list[dict[str, Any]]): A list of milestone objects representing incident events.

        Returns:
            dict[str, Any]: A dictionary containing computed incident analytics metrics.

        """

        incident_times = {
            "started": None,
            "acknowledged": None,
            "mitigated": None,
            "identified": None,
            "resolved": None,
        }

        for event in milestones:
            incident_type = event["type"]
            occurred_at = datetime.fromisoformat(event.get("occurred_at", ""))

            if incident_type in incident_times:
                if incident_times[incident_type] is None:
                    incident_times[incident_type] = occurred_at  # type: ignore
            else:
                continue  # Ignore unknown incident types
        result: dict[str, Any] = {}

        if incident_times["started"] and incident_times["acknowledged"]:
            time_to_acknowledge = (
                incident_times["acknowledged"] - incident_times["started"]
            ).total_seconds()
            result["time_to_acknowledge"] = int(time_to_acknowledge / 60)

        if incident_times["started"] and incident_times["identified"]:
            time_to_identify = (
                incident_times["identified"] - incident_times["started"]
            ).total_seconds()
            result["time_to_identify"] = int(time_to_identify / 60)

        if incident_times["started"] and incident_times["mitigated"]:
            time_to_acknowledge = (
                incident_times["mitigated"] - incident_times["started"]
            ).total_seconds()
            result["time_to_mitigate"] = int(time_to_acknowledge / 60)

        if incident_times["started"] and incident_times["resolved"]:
            time_to_resolve = (
                incident_times["resolved"] - incident_times["started"]
            ).total_seconds()
            result["time_to_resolve"] = int(time_to_resolve / 60)

        return result

    async def create_webhooks_if_not_exists(self) -> None:
        """
        Create webhooks if they do not already exist in the Firehydrant account.

        This function checks if webhooks are already configured in the Firehydrant account.
        If webhooks do not exist, it creates them. If they do exist, it takes no action.
        It uses specification from https://developers.firehydrant.com/#/operations/postV1Webhooks

        Returns:
            None: This function does not return a value
        """

        params: dict[str, Any] = {
            "page": 1,
            "per_page": PAGE_SIZE,
        }
        webhook_endpoint = "webhooks"
        all_subscriptions = await self.send_paginated_api_request(
            endpoint=webhook_endpoint, query_params=params, data_key="data"
        )

        app_host_webhook_url = f"{self.app_host}/integration/webhook"

        for webhook in all_subscriptions:
            if webhook["url"] == app_host_webhook_url:
                return

        body = {
            "url": app_host_webhook_url,
            "state": "active",
            "subscriptions": ["incidents"],
        }

        await self.send_api_request(
            endpoint=webhook_endpoint, method="POST", json_data=body
        )
