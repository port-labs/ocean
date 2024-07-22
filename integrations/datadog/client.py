import datetime
import http
import json
from typing import Any, AsyncGenerator, Optional
from urllib.parse import urlparse, urlunparse

import httpx
from loguru import logger

from utils import transform_period_of_time_in_days_to_timestamps
from port_ocean.utils import http_async_client
from port_ocean.utils.queue_utils import process_in_queue

MAX_PAGE_SIZE = 100
MAX_CONCURRENT_REQUESTS = 2


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
