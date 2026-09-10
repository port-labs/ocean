from typing import Any

import httpx
import jinja2
from httpx import HTTPStatusError

from linear.client.rate_limiter import LinearRateLimitStatus, parse_rate_limit_headers
from linear.helpers.exceptions import LinearActionError
from linear.queries import QUERIES


class GraphqlClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        linear_url: str,
        auth_headers: dict[str, str],
    ) -> None:
        self._http_client = http_client
        self._linear_url = linear_url
        self._auth_headers = auth_headers
        self._rate_limit_status: LinearRateLimitStatus | None = None

    def get_rate_limit_status(self) -> LinearRateLimitStatus | None:
        return self._rate_limit_status

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http_client.post(
                self._linear_url,
                json={"query": query, "variables": variables or {}},
                headers=self._auth_headers,
            )
            response.raise_for_status()
        except HTTPStatusError as error:
            raise LinearActionError.from_response(error.response) from error

        self._rate_limit_status = parse_rate_limit_headers(dict(response.headers))

        payload = response.json()
        if errors := payload.get("errors"):
            raise LinearActionError.from_graphql_errors(errors)

        data = payload.get("data")
        if not isinstance(data, dict):
            raise LinearActionError("Linear returned an empty response")

        return data

    async def execute_query_template(
        self,
        template_key: str,
        **template_vars: Any,
    ) -> dict[str, Any]:
        template = jinja2.Template(QUERIES[template_key], enable_async=True)
        query = await template.render_async(**template_vars)
        return await self.execute(query)

    async def execute_mutation(
        self,
        query: str,
        variables: dict[str, Any],
        *,
        result_key: str,
    ) -> dict[str, Any]:
        data = await self.execute(query, variables)
        result = data.get(result_key)
        if not isinstance(result, dict) or not result.get("success"):
            raise LinearActionError(
                f"Linear mutation '{result_key}' returned an unsuccessful response"
            )
        return result
