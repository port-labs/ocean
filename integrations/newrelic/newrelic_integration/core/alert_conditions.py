from typing import Any, AsyncIterable, cast, Optional
import re
import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from newrelic_integration.core.utils import send_graph_api_request
from newrelic_integration.core.query_templates.alert_conditions import (
    GET_ENTITY_TAGS_QUERY,
)
from newrelic_integration.utils import render_query


class AlertConditionsHandler:
    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client
        self.base_url = cast(
            str,
            ocean.integration_config.get("new_relic_rest_api_url"),
        )
        self.api_key = cast(str, ocean.integration_config.get("new_relic_api_key"))

    async def fetch_tags_for_entity(self, entity_guid: str) -> list[dict[str, Any]]:
        """Fetch tags for an entity using GraphQL API."""
        if not entity_guid:
            return []

        try:
            query = await render_query(GET_ENTITY_TAGS_QUERY, entity_guid=entity_guid)
            response = await send_graph_api_request(
                self.http_client,
                query=query,
                request_type="fetch_tags_for_entity",
                entity_guid=entity_guid,
            )

            entity = response.get("data", {}).get("actor", {}).get("entity", {})
            if not entity:
                logger.debug(
                    f"No entity found for guid {entity_guid}, returning empty tags"
                )
                return []

            tags = entity.get("tags", [])
            return tags
        except Exception as err:
            logger.warning(
                f"Failed to fetch tags for entity {entity_guid}, continuing",
                err=str(err),
            )
            return []

    async def list_alert_policies(self) -> list[int]:
        """Fetch all alert policy IDs using REST API."""
        url = f"{self.base_url}/v2/alerts_policies.json"
        response = await self.http_client.get(
            url,
            headers={
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        policies = data.get("policies", [])
        return [policy["id"] for policy in policies]

    def _extract_next_url_from_link_header(
        self, link_header: Optional[str]
    ) -> Optional[str]:
        """Extract the next page URL from the Link header.

        The Link header format is: <url>; rel="next" or <url>; rel='next'
        Returns the URL if rel="next" is found, None otherwise.
        """
        if not link_header:
            return None

        # Pattern to match: <url>; rel="next" or <url>; rel='next' (case-insensitive)
        # The pattern handles both single and double quotes, and case-insensitive matching
        pattern = r'<([^>]+)>;\s*rel=["\']?next["\']?'
        match = re.search(pattern, link_header, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _parse_error_message(self, error_data: Any) -> str:
        """Extract error message from API error response."""
        if isinstance(error_data, dict):
            return (
                error_data.get("title") or error_data.get("message") or str(error_data)
            )
        return str(error_data)

    def _extract_conditions_from_response(
        self, data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract conditions from API response, handling both response formats."""
        return data.get("nrql_conditions") or data.get("conditions") or []

    def _normalize_next_url(self, next_url: str) -> str:
        """Convert relative URL to absolute URL if needed."""
        if next_url.startswith("/"):
            return f"{self.base_url}{next_url}"
        if not next_url.startswith("http"):
            return f"{self.base_url}/{next_url}"
        return next_url

    async def _fetch_conditions_page(
        self, url: str, policy_id: int, params: Optional[dict[str, Any]] = None
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        """Fetch a single page of alert conditions.

        Returns:
            Tuple of (conditions_list, next_page_url). next_page_url is None if no more pages.
        """
        response = await self.http_client.get(
            url,
            headers={
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
            },
            params=params,
            timeout=30.0,
        )

        if response.status_code != 200:
            error_data = response.json()
            error_msg = self._parse_error_message(error_data.get("error", {}))
            logger.warning(
                f"Error fetching conditions for policy {policy_id}: {error_msg}"
            )
            return [], None

        data = response.json()
        if "error" in data:
            error_msg = self._parse_error_message(data.get("error", {}))
            logger.warning(
                f"Error fetching conditions for policy {policy_id}: {error_msg}"
            )
            return [], None

        conditions = self._extract_conditions_from_response(data)

        link_header = response.headers.get("Link") or response.headers.get("link")
        next_url = self._extract_next_url_from_link_header(link_header)

        if next_url:
            next_url = self._normalize_next_url(next_url)
            logger.debug(
                f"Found next page for policy {policy_id}, continuing pagination"
            )

        return conditions, next_url

    async def list_alert_conditions_for_policy(
        self, policy_id: int
    ) -> list[dict[str, Any]]:
        """Fetch NRQL alert conditions for a specific policy using REST API with pagination support."""
        all_conditions: list[dict[str, Any]] = []
        url: Optional[str] = f"{self.base_url}/v2/alerts_nrql_conditions.json"
        params: Optional[dict[str, Any]] = {"policy_id": policy_id}

        while url:
            conditions, next_url = await self._fetch_conditions_page(
                url, policy_id, params
            )
            all_conditions.extend(conditions)
            url = next_url
            # Clear params for subsequent requests since the URL already contains them
            params = None

        logger.debug(
            f"Fetched {len(all_conditions)} total conditions for policy {policy_id}"
        )
        return all_conditions

    async def enrich_condition_with_tags(
        self, condition: dict[str, Any]
    ) -> dict[str, Any]:
        """Enrich a condition with tags from its entity_guid."""
        entity_guid = condition.get("entity_guid")
        if entity_guid:
            tags = await self.fetch_tags_for_entity(entity_guid)
            # Format tags similar to how entities format them
            condition["tags"] = {tag["key"]: tag["values"] for tag in tags}
        else:
            condition["tags"] = {}
        return condition

    async def list_alert_conditions(self) -> AsyncIterable[dict[str, Any]]:
        """List all alert conditions with their policy_id and tags."""
        policies = await self.list_alert_policies()
        logger.info(f"Found {len(policies)} alert policies")

        for policy_id in policies:
            conditions = await self.list_alert_conditions_for_policy(policy_id)
            logger.debug(f"Found {len(conditions)} conditions for policy {policy_id}")

            for condition in conditions:
                # Add policy_id to condition
                condition["policy_id"] = policy_id
                # Enrich with tags
                enriched_condition = await self.enrich_condition_with_tags(condition)
                yield enriched_condition
