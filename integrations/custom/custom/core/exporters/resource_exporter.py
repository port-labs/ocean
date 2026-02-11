import functools
from typing import AsyncGenerator, Dict, List, Any

from loguru import logger

from custom.clients.http.client import HttpServerClient
from custom.core.exporters.abstract_exporter import AbstractHttpExporter
from custom.core.options import FetchResourceOptions
from custom.helpers.endpoint_resolver import resolve_dynamic_endpoints
from custom.helpers.utils import (
    process_endpoints_concurrently,
    extract_and_enrich_batch,
    DEFAULT_CONCURRENCY_LIMIT,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class HttpResourceExporter(AbstractHttpExporter[HttpServerClient]):
    """Exporter for HTTP endpoint resources.

    Handles dynamic endpoint resolution, paginated data fetching,
    and data extraction using JQ data_path expressions.
    """

    def __init__(self, client: HttpServerClient) -> None:
        super().__init__(client)

    async def get_paginated_resources(
        self, options: FetchResourceOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        kind = options["kind"]
        selector = options["selector"]

        method = selector.method
        query_params = selector.query_params or {}
        headers = selector.headers or {}
        body = getattr(selector, "body", None)
        data_path = selector.data_path or "."

        logger.info(f"Starting export for kind (endpoint): {kind}")

        async for endpoint_batch in resolve_dynamic_endpoints(selector, kind):
            async for batch in process_endpoints_concurrently(
                endpoints=endpoint_batch,
                fetch_fn=functools.partial(
                    self._fetch_endpoint_data,
                    method=method,
                    query_params=query_params,
                    headers=headers,
                    body=body,
                    data_path=data_path,
                ),
                concurrency_limit=DEFAULT_CONCURRENCY_LIMIT,
            ):
                yield batch

    async def _fetch_endpoint_data(
        self,
        endpoint: str,
        path_params: Dict[str, str],
        *,
        method: str,
        query_params: Dict[str, Any],
        headers: Dict[str, str],
        body: Any,
        data_path: str,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch and process data from a single endpoint."""
        logger.info(f"Fetching data from: {method} {endpoint}")

        try:
            async for batch in self.client.fetch_paginated_data(
                endpoint=endpoint,
                method=method,
                query_params=query_params,
                headers=headers,
                body=body,
            ):
                logger.info(f"Received {len(batch)} records from {endpoint}")

                if data_path == "." and batch and not isinstance(batch[0], list):
                    logger.warning(
                        f"Response from {endpoint} is not a list and 'data_path' is not specified. "
                        f"Yielding response as-is. If mapping fails, please specify 'data_path' in your selector "
                        f"(e.g., data_path: '.data'). Response type: {type(batch[0]).__name__}"
                    )
                    yield batch
                    continue

                processed_batch = extract_and_enrich_batch(
                    batch, data_path, path_params, endpoint
                )

                if processed_batch:
                    logger.info(
                        f"Extracted {len(processed_batch)} items using data_path: {data_path}"
                    )
                    yield processed_batch

        except Exception as e:
            logger.error(f"Error fetching data from {endpoint}: {str(e)}")
