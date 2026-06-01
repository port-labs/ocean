import asyncio
import time
from typing import Any, TypedDict

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base import PaginatedExporter
from datadog.core.exporters.service import ServiceExporter

SERVICE_KEY = "__service"
QUERY_ID_KEY = "__query_id"
QUERY_KEY = "__query"
ENV_KEY = "__env"
FETCH_WINDOW_TIME_IN_MINUTES = 10


class ServiceMetricOptions(TypedDict):
    metric_query: str
    env_tag: str
    env_value: str
    service_tag: str
    service_value: str
    time_window_in_minutes: int


class ServiceMetricExporter(PaginatedExporter[ServiceMetricOptions]):
    async def get_paginated_resources(
        self, options: ServiceMetricOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Fetch metrics for services and environments."""
        metric_query = options["metric_query"]
        env_tag = options["env_tag"]
        env_value = options["env_value"]
        service_tag = options["service_tag"]
        service_value = options["service_value"]
        time_window_in_minutes = options["time_window_in_minutes"]

        logger.info(
            f"Fetching metrics for query: {metric_query} | env_tag: {env_tag}, env_value: {env_value} | "
            f"service_tag: {service_tag}, service_value: {service_value}"
        )

        envs_to_fetch = (
            [env_value]
            if env_value != "*"
            else self._get_env_tags(await self._get_tags(), env_tag)
        )
        if not envs_to_fetch:
            logger.warning(
                f"No environments found, can't fetch metrics for metric {metric_query}"
            )
            return

        service_exporter = ServiceExporter(self.client)

        if service_value == "*":
            async for service_list in service_exporter.get_paginated_resources():
                async for metrics in self._fetch_metrics_for_services(
                    metric_query,
                    envs_to_fetch,
                    service_list,
                    time_window_in_minutes,
                    env_tag,
                    service_tag,
                ):
                    yield metrics
        else:
            result = await service_exporter.get_resource(service_value)
            if not result:
                return
            service_details: dict[str, Any] = result["data"]
            async for metrics in self._fetch_metrics_for_services(
                metric_query,
                envs_to_fetch,
                [service_details],
                time_window_in_minutes,
                env_tag,
                service_tag,
            ):
                yield metrics

    async def _get_tags(self) -> dict[str, Any]:
        url = f"{self.client.api_url}/api/v1/tags/hosts"
        result = await self.client.send_api_request(url)
        return result.get("tags")

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

                task = asyncio.create_task(
                    self.client.send_rate_limited_request(
                        url, semaphore=self.client._metrics_semaphore
                    )
                )
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
