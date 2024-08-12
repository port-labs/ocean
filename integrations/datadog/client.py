import asyncio
import re
import datetime
import http
import json
import time
from typing import Any, AsyncGenerator, Callable, Optional
from urllib.parse import urlparse, urlunparse

import httpx
from loguru import logger

from utils import transform_period_of_time_in_days_to_timestamps
from port_ocean.utils import http_async_client
from port_ocean.utils.queue_utils import process_in_queue

MAX_PAGE_SIZE = 100
MAX_CONCURRENT_REQUESTS = 2

MAXIMUM_CONCURRENT_REQUESTS_METRICS = 20
MAXIMUM_CONCURRENT_REQUESTS_DEFAULT = 1
MINIMUM_LIMIT_REMAINING = 1
DEFAULT_SLEEP_TIME = 0.1


def embed_credentials_in_url(url: str, username: str, token: str) -> str:
    """
    Inserts username and token into a given URL for Datadog compatibility.

    This method prepares a URL for use with Datadog webhook integrations.
    Datadog's webhooks can utilize basic HTTP authentication, requiring credentials embedded within the URL.

    Args:
        url (str): The original URL.
        username (str): The username to insert.
        token (str): The token (likely an API key) to insert.

    Returns:
        str: The modified URL with inserted credentials, ready for Datadog use.

    Example:
        new_url = embed_credentials_in_url("https://my.service.example.com", "my_username", "my_api_key")
        # Use new_url in your Datadog webhook configuration
    """
    parsed_url = urlparse(url)

    # Insert credentials into the netloc part of the URL
    netloc_with_credentials = f"{username}:{token}@{parsed_url.netloc}"

    # Create a new URL with inserted credentials
    modified_url = urlunparse(
        (
            parsed_url.scheme,
            netloc_with_credentials,
            parsed_url.path,
            parsed_url.params,
            parsed_url.query,
            parsed_url.fragment,
        )
    )

    return modified_url


class DatadogClient:
    def __init__(self, api_url: str, api_key: str, app_key: str):
        self.api_url = api_url
        self.dd_api_key = api_key
        self.dd_app_key = app_key

        self.http_client = http_async_client

        # These are created to limit the concurrent requests we are making to specific routes.
        # The limits provided to each semaphore were pre-determined by the headers sent for each one of the routes.
        # For more information about Datadog's rate limits, please read this: https://docs.datadoghq.com/api/latest/rate-limits/
        self._default_semaphore = asyncio.Semaphore(MAXIMUM_CONCURRENT_REQUESTS_DEFAULT)
        self._metrics_semaphore = asyncio.Semaphore(MAXIMUM_CONCURRENT_REQUESTS_METRICS)

    @property
    def datadog_web_url(self) -> str:
        """Replaces 'api' with 'app' in Datadog URLs."""
        return re.sub(r"https://api\.", "https://app.", self.api_url)

    @property
    async def auth_headers(self) -> dict[str, Any]:
        return {
            "DD-API-KEY": self.dd_api_key,
            "DD-APPLICATION-KEY": self.dd_app_key,
            "Content-Type": "application/json",
        }

    async def _send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        logger.debug(f"Sending request {method} to endpoint {url}")

        response = await self.http_client.request(
            url=url,
            method=method,
            headers=await self.auth_headers,
            params=params,
            json=json_data,
        )
        response.raise_for_status()
        return response.json()

    async def _fetch_with_rate_limit_handling(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> Any:
        if semaphore is None:
            semaphore = self._default_semaphore

        while True:
            async with semaphore:
                response = await self.http_client.request(
                    url=url,
                    method=method,
                    headers=await self.auth_headers,
                    params=params,
                    json=json_data,
                )
            try:
                rate_limit_remaining = int(
                    response.headers.get("X-RateLimit-Remaining", 0)
                )
                if rate_limit_remaining <= MINIMUM_LIMIT_REMAINING:
                    datadog_wait_time_in_seconds = int(
                        response.headers.get("X-RateLimit-Reset")
                    )
                    wait_time = max(datadog_wait_time_in_seconds, DEFAULT_SLEEP_TIME)

                    logger.info(
                        f"Approaching rate limit. Waiting for {wait_time} seconds before retrying. "
                        f"URL: {url}, Remaining: {rate_limit_remaining} "
                    )
                    await asyncio.sleep(wait_time)
            except KeyError as e:
                logger.warning(
                    f"Rate limit headers not found in response: {str(e)} for url {url}"
                )
            except Exception as e:
                logger.error(f"Error while making request to url: {url} - {str(e)}")
                raise
            return response.json()

    async def get_hosts(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        start = 0
        count = MAX_PAGE_SIZE

        while True:
            url = f"{self.api_url}/api/v1/hosts"
            result = await self._send_api_request(
                url, params={"start": start, "count": count}
            )

            hosts = result.get("host_list")
            if not hosts:
                break

            yield hosts
            start += count

    async def get_monitors(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        page = 0
        page_size = MAX_PAGE_SIZE

        while True:
            url = f"{self.api_url}/api/v1/monitor"
            monitors = await self._send_api_request(
                url, params={"page": page, "page_size": page_size}
            )

            if not monitors:
                break

            yield monitors
            page += 1

    async def get_services(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        page = 0
        page_size = MAX_PAGE_SIZE

        while True:
            url = f"{self.api_url}/api/v2/services/definitions"
            result = await self._send_api_request(
                url,
                params={
                    "page[number]": page,
                    "page[size]": page_size,
                    "schema_version": "v2.2",
                },
            )

            services = result.get("data")
            if not services:
                break

            yield services
            page += 1

    async def get_slos(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Asynchronously fetches Datadog SLOs (Service Level Objectives).

        This method retrieves SLOs from Datadog, handling pagination to ensure
        all SLOs are fetched.

        Yields:
            List[Dict[str, Any]]: A list of dictionaries representing Datadog SLOs.

        Returns:
            AsyncGenerator: An asynchronous generator yielding lists of SLOs.

        Example:
            async for slo_batch in your_instance.get_slos():
                process_slo_batch(slo_batch)
        """
        offset = 0
        limit = MAX_PAGE_SIZE

        while True:
            url = f"{self.api_url}/api/v1/slo"
            result = await self._send_api_request(
                url, params={"limit": limit, "offset": offset}
            )

            slos = result.get("data")
            if not slos:
                break

            yield slos
            offset += limit

    async def list_slo_histories(
        self, timeframe: int, period_of_time_in_months: int
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        timestamps = transform_period_of_time_in_days_to_timestamps(
            timeframe, period_of_time_in_months
        )
        async for slos in self.get_slos():
            for from_ts, to_ts in timestamps:
                histories = await process_in_queue(
                    [slo["id"] for slo in slos],
                    self.get_slo_history,
                    timeframe,
                    from_ts,
                    to_ts,
                    concurrency=MAX_CONCURRENT_REQUESTS,
                )
                yield [history for history in histories if history]

    async def get_slo_history(
        self, slo_id: str, timeframe: int, from_ts: int, to_ts: int
    ) -> dict[str, Any]:
        url = f"{self.api_url}/api/v1/slo/{slo_id}/history"
        readable_from_ts = datetime.datetime.fromtimestamp(from_ts)
        readable_to_ts = datetime.datetime.fromtimestamp(to_ts)
        try:
            logger.info(
                f"Fetching SLO history for {slo_id} from {readable_from_ts} to {readable_to_ts} in time range of {timeframe} days"
            )
            result = await self._send_api_request(
                url, params={"from_ts": from_ts, "to_ts": to_ts}
            )
            # res = result.get("data")
            return {**result.get("data"), "__timeframe": timeframe}
        except httpx.HTTPStatusError as err:
            if err.response.status_code == http.HTTPStatus.BAD_REQUEST:
                if (
                    "The timeframe is incorrect: slo from_ts must be"
                    in err.response.text
                ):
                    logger.info(
                        f"Slo {slo_id} has no history for the given timeframe {readable_from_ts}, {readable_to_ts} in time range of {timeframe} days"
                    )
                    return {}
                if (
                    "Queries ending outside the retention date are invalid"
                    in err.response.text
                ):
                    logger.info(
                        f"Slo {slo_id} has no history for the given timeframe {readable_from_ts}, {readable_to_ts} in time range of {timeframe} days"
                    )
                    return {}
            logger.info(
                f"Failed to fetch SLO history for {slo_id}: {err}, {err.response.text}, for the given timeframe {readable_from_ts}, {readable_to_ts} in time range of {timeframe} days"
            )
            return {}

    async def check_metric_data_exists(
        self, query: str, time_in_minutes: int = 10
    ) -> bool:
        """
        Queries the Datadog API to check if there is any data for a given metric query within a specified time window.

        Args:
            query: The Datadog metric query string e.g. "avg:container.cpu.usage{service:payments-app}".
            time_in_minutes: The time window (in minutes) to look back for data (default: 10 minutes).

        Returns:
            True if the query returns at least one data series, False otherwise (including errors or rate limiting).
        """
        end_time = int(time.time())
        start_time = end_time - (time_in_minutes * 60)

        url = (
            f"{self.api_url}/api/v1/query?from={start_time}&to={end_time}&query={query}"
        )
        result = await self._fetch_with_rate_limit_handling(
            url, semaphore=self._metrics_semaphore
        )

        if result.get("status") == "ok":
            # Check if the series list is populated
            if "series" in result and result["series"]:
                return True
            else:
                return False
        elif result.get("status") == "error" and result.get("code") == 429:
            logger.error(f"Rate limit exceeded: {result.get('error')}")
            return False
        else:
            logger.error(f"Error fetching data: {result.get('error')}")
            return False

    def _create_query_with_values(
        self, metric_query: str, variable_values: dict[str, str]
    ) -> str:
        """
        Creates a Datadog query by substituting template variables with their values.

        Args:
            metric_query (str): The original query string containing template variables (e.g., "avg:container.cpu.usage{$service}").
            variable_values (dict): A dictionary mapping variable names to their values (e.g., {"service": "svc_name", "env": "prod"}).

        Returns:
            str: The modified query with variables replaced by their values.
        """
        logger.debug(f"Creating query with values: {metric_query} | {variable_values}")
        for variable_name, value in variable_values.items():
            metric_query = metric_query.replace(
                f"${variable_name}", f"{variable_name}:{value}"
            )
        return metric_query

    def _extract_queries_with_template_variable(
        self, dashboard_json: dict[str, Any], variable_name: str
    ) -> list[dict[str, Any]]:
        """
        Extracts metric queries from a Datadog dashboard JSON that use a specified template variable, grouping queries by widget.

        Args:
            dashboard_json (dict): The dashboard data as a Python dictionary.
            variable_name (str): The name of the template variable to search for (e.g., "service").

        Returns:
            list: A list of dictionaries, each containing the widget ID, widget title, and a list of queries.
        """
        filter_name = f"${variable_name}"
        matching_queries = {}

        for widget in dashboard_json["widgets"]:
            queries = [
                query["query"]
                for request in widget["definition"].get("requests", [])
                for query in request.get("queries", [])
                if filter_name in query["query"]
            ]

            if queries:
                matching_queries[widget["id"]] = {
                    "widget_id": widget["id"],
                    "widget_title": widget["definition"].get("title", "Untitled"),
                    "queries": queries,
                }

        return list(matching_queries.values())

    async def get_single_dashboard(self, dashboard_id: str) -> dict[str, Any] | None:
        if not dashboard_id:
            return None
        url = f"{self.api_url}/api/v1/dashboard/{dashboard_id}"
        return await self._send_api_request(url)

    async def enrich_dashboard_url(self, dashboard: dict[str, Any]) -> dict[str, Any]:
        """
        Enriches a dashboard item with the full Datadog web URL.
        """
        dashboard["url"] = f"{self.datadog_web_url}{dashboard['url']}"
        return dashboard

    async def get_dashboards(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        page = 0
        page_size = MAX_PAGE_SIZE

        while True:
            url = f"{self.api_url}/api/v1/dashboard"
            result = await self._send_api_request(
                url,
                params={
                    "start": page,
                    "count": page_size,
                    "filter[shared]": "false",
                    "filter[deleted]": "false",
                },
            )
            dashboards = result.get("dashboards")
            if not dashboards:
                break

            # Enrich items concurrently using asyncio.gather
            dashboards = await asyncio.gather(
                *[self.enrich_dashboard_url(dashboard) for dashboard in dashboards]
            )

            yield dashboards
            page += 1

    async def add_dashboard_id_to_widget(
        self, widget: dict[str, Any], dashboard_id: str
    ) -> dict[str, Any]:
        """
        Adds the dashboard ID to a widget dictionary.
        """
        widget["dashboard_id"] = dashboard_id
        return widget

    async def get_dashboard_metrics(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Asynchronously fetches and yields lists of widgets (metrics) from multiple Datadog dashboards.

        This method retrieves dashboards in batches, processes them concurrently to extract widgets (metrics),
        and yields each list of widgets as they become available.

        Yields:
            Lists of dictionaries, where each dictionary represents a widget (metric) from a Datadog dashboard.
            The structure of each widget dictionary depends on the Datadog API response.
        """
        async for dashboards in self.get_dashboards():
            metrics = await process_in_queue(
                [dashboard["id"] for dashboard in dashboards],
                self.get_single_dashboard,
                concurrency=MAX_CONCURRENT_REQUESTS,
            )

            for metric in metrics:
                if metric and (widgets := metric.get("widgets")):
                    # Filter out widgets with 'definition.type' == 'group' since they are usually containers for other widgets
                    filtered_widgets = [
                        widget
                        for widget in widgets
                        if widget.get("definition", {}).get("type") != "group"
                    ]

                    # Add dashboard_id to each filtered widget
                    await asyncio.gather(
                        *[
                            self.add_dashboard_id_to_widget(widget, metric["id"])
                            for widget in filtered_widgets
                        ]
                    )

                    yield filtered_widgets

    async def fetch_dashboard_by_id(self, dashboard_id: str) -> Optional[dict[str, Any]]:
        dashboard = await self.get_single_dashboard(dashboard_id)
        if not dashboard:
            logger.error(f"Failed to fetch dashboard {dashboard_id}")
            return None

        widgets = dashboard.get("widgets")
        if not widgets:
            logger.error(f"Dashboard {dashboard_id} has no widgets")
            return None

        template_variables = dashboard.get("template_variables")
        if not template_variables:
            logger.error(f"Dashboard {dashboard_id} has no template variables")
            return None

        return dashboard

    async def check_metrics_availability(
        self,
        template_var: str,
        template_var_value: str,
        widgets: list[dict[str, Any]],
        default_env: str = "",
    ) -> dict[str, Any]:
        """
        Checks the availability of metrics for an item (e.g., service, host) across multiple widgets in a Datadog dashboard.

        Args:
            template_var: The name of the template variable used in the queries (e.g., "service", "host").
            template_var_value: The value of the template variable to substitute in the queries (e.g., "service-name", "hostname").
            widgets: A list of dictionaries, each containing information about a widget:
                * widget_id: The ID of the widget.
                * widget_title: The title of the widget (generated if empty).
                * queries: A list of metric queries associated with the widget.
            default_env: The default environment to use if the dashboard has an "env" template variable (optional).

        Returns:
            A dictionary mapping widget IDs to their metric availability status. Each entry includes:
                * widget_id: The ID of the widget.
                * widget_title: The title of the widget.
                * widget_metrics_status: A list of dictionaries, each containing:
                    * metric: The specific metric query.
                    * has_data: True if the metric has data for the given item, False otherwise.
                * has_all_metrics: True if all metrics in the widget have data for the item, False otherwise.
        """
        metrics_availability: dict[str, Any] = {}

        for widget in widgets:
            widget_id, widget_title, queries = widget.values()
            logger.info(
                f"Processing widget {widget_id} ({widget_title}) for {template_var} {template_var_value}"
            )

            widget_metrics = metrics_availability.setdefault(
                f"widget_id_{widget_id}",
                {
                    "widget_id": widget_id,
                    "widget_title": widget_title,
                    "widget_metrics_status": [],
                    "has_all_metrics": True,
                },
            )

            for query in queries:
                query_with_values = self.create_query_with_values(
                    query, {template_var: template_var_value, "env": default_env}
                )

                has_data = await self.check_metric_data_exists(
                    query_with_values, time_in_minutes=10
                )

                widget_metrics["widget_metrics_status"].append(
                    {"metric": query_with_values, "has_data": has_data}
                )
                if not has_data:
                    widget_metrics["has_all_metrics"] = False

        return metrics_availability

    async def enrich_kind_with_dashboard_metrics(
        self,
        dashboard_id: str,
        items: list[dict[str, Any]],
        template_var: str = "service",
        item_name_extractor: Callable[[dict[str, Any]], str] = lambda item: item[
            "attributes"
        ]["schema"]["dd-service"],
    ) -> list[dict[str, Any]]:
        """
        Enriches a list of Datadog items (e.g., services, hosts) with information about the availability of metrics
        from a specified dashboard.

        This function checks whether metric data exists for each item within the given dashboard's widgets that use
        the specified template variable. It updates the items in the list with a new key, "__metrics_availability",
        containing details about the status of metrics for each relevant widget in the dashboard.

        Args:
            dashboard_id: The ID of the Datadog dashboard to check for metrics.
            items: A list of dictionaries representing the Datadog items (e.g., services, hosts) to enrich.
            template_var: The name of the template variable used in the dashboard's widgets to filter items
                        (e.g., "service", "host"). Defaults to "service".
            item_name_extractor: A function that takes an item dictionary as input and returns the relevant
                                item name used for metric queries (e.g., service name, hostname).
                                Defaults to extracting the "dd-service" value from the "schema" within the
                                item's "attributes".

        Returns:
            The list of enriched item dictionaries, where each dictionary now includes a "__metrics_availability" key.
            This key contains information about whether metrics are available for the item in each relevant widget of
            the dashboard.
        """
        dashboard = await self.validate_dashboard(dashboard_id)
        if not dashboard:
            logger.error(f"Failed to fetch dashboard {dashboard_id}")
            return items

        if not any(
            tv.get("name") == template_var for tv in dashboard["template_variables"]
        ):
            logger.error(
                f"Dashboard {dashboard_id} missing '{template_var}' template variable"
            )
            return items

        widgets = self.extract_queries_with_template_variable(dashboard, template_var)
        if not widgets:
            logger.error(
                f"No widgets with '{template_var}' queries found in dashboard {dashboard_id}"
            )
            return items

        logger.info(
            f"Enriching {len(items)} items with metrics from {len(widgets)} widgets in '{dashboard['title']}'"
        )

        # Check if the dashboard uses an "env" template variable, and if so, retrieve its default value.
        # This allows us to include the default environment in metric queries if it's defined.
        # https://docs.datadoghq.com/getting_started/tagging/
        default_env = next(
            (
                var.get("default")
                for var in dashboard["template_variables"]
                if var["name"] == "env"
            ),
            "",
        )

        for item in items:
            item_name = item_name_extractor(item)
            dashboard_key = re.sub(r"[\s-]+", "_", dashboard["title"].strip().lower())

            dashboard_metrics = item.setdefault(
                "__metrics_availability", {}
            ).setdefault(
                dashboard_key,
                {
                    "id": dashboard["id"],
                    "title": dashboard["title"],
                    "url": f"{self.datadog_web_url}/{dashboard['url']}",
                    "has_all_metrics": True,  # Initial assumption
                    "widget_metrics": {},
                },
            )

            metrics_availability = await self.check_metrics_availability(
                template_var,
                template_var_value=item_name,
                widgets=widgets,
                default_env=default_env,
            )

            if not all(
                widget_metrics["has_all_metrics"]
                for widget_metrics in metrics_availability.values()
            ):
                dashboard_metrics["has_all_metrics"] = False

            dashboard_metrics["widget_metrics"].update(metrics_availability)

            # Add an array of available metrics to the item
            available_metrics = [
                widget_metrics
                for widget_metrics in metrics_availability.values()
                if widget_metrics["has_all_metrics"]
            ]

            item["__available_metrics"] = available_metrics

        return items

    async def get_single_monitor(self, monitor_id: str) -> dict[str, Any] | None:
        if not monitor_id:
            return None
        url = f"{self.api_url}/api/v1/monitor/{monitor_id}"
        return await self._send_api_request(url)

    async def create_webhooks_if_not_exists(self, app_host: Any, token: Any) -> None:
        dd_webhook_url = (
            f"{self.api_url}/api/v1/integration/webhooks/configuration/webhooks"
        )

        try:
            webhook = await self._send_api_request(
                url=f"{dd_webhook_url}/PORT", method="GET"
            )
            if webhook:
                logger.info(f"Webhook already exists: {webhook}")
                return
        except httpx.HTTPStatusError as err:
            if err.response.status_code == 404:
                # Webhook does not exist, continue with creation
                pass
            elif err.response.status_code == 500:
                # Webhooks are not yet enabled in Datadog
                logger.error(err.response.text)
                raise err
            else:
                raise

        logger.info("Subscribing to Datadog webhooks...")

        app_host_webhook_url = f"{app_host}/integration/webhook"
        modified_url = embed_credentials_in_url(app_host_webhook_url, "port", token)

        body = {
            "name": "PORT",
            "url": modified_url,
            "encode_as": "json",
            "payload": json.dumps(
                {
                    "id": "$ID",
                    "message": "$TEXT_ONLY_MSG",
                    "priority": "$PRIORITY",
                    "last_updated": "$LAST_UPDATED",
                    "event_type": "$EVENT_TYPE",
                    "event_url": "$LINK",
                    "service": "$HOSTNAME",
                    "creator": "$USER",
                    "title": "$EVENT_TITLE",
                    "date": "$DATE",
                    "org_id": "$ORG_ID",
                    "org_name": "$ORG_NAME",
                    "alert_id": "$ALERT_ID",
                    "alert_metric": "$ALERT_METRIC",
                    "alert_status": "$ALERT_STATUS",
                    "alert_title": "$ALERT_TITLE",
                    "alert_type": "$ALERT_TYPE",
                    "tags": "$TAGS",
                    "body": "$EVENT_MSG",
                }
            ),
        }

        logger.info("Creating webhook subscription")
        result = await self._send_api_request(
            url=dd_webhook_url, method="POST", json_data=body
        )

        logger.info(f"Webhook Subscription Response: {result}")
