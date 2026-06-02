import asyncio
import time
from typing import Any

from loguru import logger
from pydantic import BaseModel
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.client import DatadogClient
from datadog.core.exporters.base_exporter import PaginatedExporter
from datadog.core.exporters.service_exporter import ServiceExporter

SERVICE_KEY = "__service"
QUERY_ID_KEY = "__query_id"
QUERY_KEY = "__query"
ENV_KEY = "__env"
FETCH_WINDOW_TIME_IN_MINUTES = 10

MAXIMUM_CONCURRENT_REQUESTS = 20
MINIMUM_LIMIT_REMAINING = 1
DEFAULT_SLEEP_TIME = 0.1


class ListServiceMetricOptions(BaseModel):
    metric_query: str
    env_tag: str = "env"
    env_value: str = "*"
    service_tag: str = "service"
    service_value: str = "*"
    time_window_in_minutes: int = 60


class ServiceMetricExporter(PaginatedExporter[ListServiceMetricOptions]):
    def __init__(self, client: DatadogClient) -> None:
        super().__init__(client)
        self._semaphore = asyncio.Semaphore(MAXIMUM_CONCURRENT_REQUESTS)

    async def _send_rate_limited_request(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        method: str = "GET",
    ) -> Any:
        """Send request with proactive rate-limit backoff."""
        while True:
            async with self._semaphore:
                response = await self.client.http_client.request(
                    url=url,
                    method=method,
                    headers=await self.client.auth_headers,
                    params=params,
                )

            self.client._log_rate_limit_context(url, method, response)
            response.raise_for_status()

            try:
                rate_limit_remaining = int(
                    response.headers.get("X-RateLimit-Remaining", 0)
                )
                if rate_limit_remaining <= MINIMUM_LIMIT_REMAINING:
                    rate_limit_reset = response.headers.get("X-RateLimit-Reset")
                    if rate_limit_reset is None:
                        logger.warning(
                            f"Approaching rate limit but X-RateLimit-Reset header missing for url {url}"
                        )
                        await asyncio.sleep(DEFAULT_SLEEP_TIME)
                        continue

                    datadog_wait_time_in_seconds = int(rate_limit_reset)
                    wait_time = max(datadog_wait_time_in_seconds, DEFAULT_SLEEP_TIME)

                    logger.info(
                        f"Approaching rate limit. Waiting for {wait_time} seconds before retrying. "
                        f"URL: {url}, Remaining: {rate_limit_remaining} "
                    )
                    await asyncio.sleep(wait_time)
                    continue
            except ValueError as e:
                logger.warning(
                    f"Invalid rate limit header value for url {url}: {str(e)}"
                )
            except Exception as e:
                logger.error(f"Error while making request to url: {url} - {str(e)}")
                raise

            return response.json()

    async def get_paginated_resources(
        self, options: ListServiceMetricOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Fetch metrics for services and environments."""
        logger.info(
            f"Fetching metrics for query: {options.metric_query} | env_tag: {options.env_tag}, env_value: {options.env_value} | "
            f"service_tag: {options.service_tag}, service_value: {options.service_value}"
        )

        envs_to_fetch = (
            [options.env_value]
            if options.env_value != "*"
            else self._get_env_tags(await self._get_tags(), options.env_tag)
        )
        if not envs_to_fetch:
            logger.warning(
                f"No environments found, can't fetch metrics for metric {options.metric_query}"
            )
            return

        service_exporter = ServiceExporter(self.client)

        if options.service_value == "*":
            async for service_list in service_exporter.get_paginated_resources():
                async for metrics in self._fetch_metrics_for_services(
                    options.metric_query,
                    envs_to_fetch,
                    service_list,
                    options.time_window_in_minutes,
                    options.env_tag,
                    options.service_tag,
                ):
                    yield metrics
        else:
            result = await service_exporter.get_resource(options.service_value)
            if not result:
                return
            service_details: dict[str, Any] = result["data"]
            async for metrics in self._fetch_metrics_for_services(
                options.metric_query,
                envs_to_fetch,
                [service_details],
                options.time_window_in_minutes,
                options.env_tag,
                options.service_tag,
            ):
                yield metrics

    async def _get_tags(self) -> dict[str, Any]:
        url = f"{self.client.api_url}/api/v1/tags/hosts"
        result = await self.client.send_api_request(url)
        return result.get("tags", {})

    @staticmethod
    def _get_env_tags(tags: dict[str, Any], tag_name: str = "env") -> list[str]:
        return [tag.split(":")[1] for tag in tags.keys() if tag.startswith(tag_name)]

    @staticmethod
    def _create_query_with_values(
        metric_query: str, variable_values: dict[str, str]
    ) -> str:
        for variable_name, value in variable_values.items():
            metric_query = metric_query.replace(
                f"${variable_name}", f"{variable_name}:{value}"
            )
        return metric_query

    async def _fetch_metrics_for_services(
        self,
        query: str,
        envs_to_fetch: list[str],
        services: list[dict[str, Any]],
        timeframe: int,
        env_tag: str = "env",
        service_tag: str = "service",
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info(
            f"Fetching metrics for {len(services)} services and {len(envs_to_fetch)} environments. "
            f"env_tag: {env_tag}, service_tag: {service_tag}"
        )

        for service in services:
            service_id = service["attributes"]["schema"]["dd-service"]

            tasks = []
            for env_to_fetch in envs_to_fetch:
                params = {service_tag: service_id, env_tag: env_to_fetch}
                query_with_values = self._create_query_with_values(
                    f"{query}{{{service_tag}:{service_id}, {env_tag}:{env_to_fetch}}}",
                    params,
                )

                end_time = int(time.time())
                start_time = end_time - (timeframe * 60)

                url = f"{self.client.api_url}/api/v1/query?from={start_time}&to={end_time}&query={query_with_values}"

                task = asyncio.create_task(self._send_rate_limited_request(url))
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            metrics = []
            for result, env_to_fetch in zip(results, envs_to_fetch):
                result.update(
                    {
                        SERVICE_KEY: service_id,
                        QUERY_ID_KEY: (
                            f"{query}/{service_tag}:{service_id}/{env_tag}:{env_to_fetch}"
                        ),
                        QUERY_KEY: query,
                        ENV_KEY: env_to_fetch,
                    }
                )
                metrics.append(result)

            yield metrics
