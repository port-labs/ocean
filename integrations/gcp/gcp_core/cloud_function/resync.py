import typing
from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger

from gcp_core.cloud_function.auth import get_id_token
from gcp_core.cloud_function.client import CloudFunctionClient
from gcp_core.overrides import GCPCloudFunctionResourceConfig


async def resync_cloud_function_resources(
    config: GCPCloudFunctionResourceConfig,
    agent: str,
    secrets: dict[str, Any],
) -> AsyncGenerator[list[dict[str, Any]], None]:
    function_url = config.selector.function_url
    resource = config.selector.resource

    async def _token_supplier() -> typing.Optional[str]:
        return await get_id_token(function_url)

    client = CloudFunctionClient(
        agent=agent,
        function_url=function_url,
        secrets=secrets,
        token_supplier=_token_supplier,
    )
    logger.info(f"Syncing resource={resource!r} via cloud function at {function_url!r}")
    async for page in client.send_paginated_request(resource):
        yield page
