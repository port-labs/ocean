from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient

from plain.exceptions import PlainGraphQLError, PlainHTTPError

DEFAULT_API_URL = "https://core-api.uk.plain.com/graphql/v1"
USER_AGENT = "port-ocean-plain"


class PlainClient:
    """Authenticated client for Plain's GraphQL API."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        config = ocean.integration_config
        self._api_token = str(config["api_token"])
        api_url = config.get("api_url") or DEFAULT_API_URL
        self._api_url = str(api_url).rstrip("/")
        self._http_client = http_client or OceanAsyncClient(
            timeout=ocean.config.client_timeout,
            headers={"User-Agent": USER_AGENT},
        )

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query, "variables": variables or {}}
        if operation_name is not None:
            body["operationName"] = operation_name

        logger.debug(
            "Executing Plain GraphQL operation {}", operation_name or "anonymous"
        )
        response = await self._http_client.post(
            self._api_url,
            json=body,
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        if response.status_code >= 400:
            raise PlainHTTPError(response.status_code, response.text)

        try:
            payload = response.json()
        except ValueError as error:
            raise PlainGraphQLError(
                [{"message": "Plain returned a non-JSON response"}]
            ) from error

        if not isinstance(payload, dict):
            raise PlainGraphQLError(
                [{"message": "Plain returned a response that is not an object"}]
            )

        errors = payload.get("errors")
        if errors:
            if not isinstance(errors, list):
                errors = [{"message": str(errors)}]
            raise PlainGraphQLError(errors)

        data = payload.get("data")
        if not isinstance(data, dict):
            raise PlainGraphQLError(
                [{"message": "Plain returned a response without data"}]
            )
        return data
