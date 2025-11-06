from typing import Any, AsyncIterable, cast
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

    async def list_alert_conditions_for_policy(
        self, policy_id: int
    ) -> list[dict[str, Any]]:
        """Fetch NRQL alert conditions for a specific policy using REST API."""
        url = f"{self.base_url}/v2/alerts_nrql_conditions.json"
        params = {"policy_id": policy_id}
        response = await self.http_client.get(
            url,
            headers={
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
            },
            params=params,
            timeout=30.0,
        )

        # Check for API errors
        if response.status_code != 200:
            error_data = response.json()
            error_msg = error_data.get("error", {})
            if isinstance(error_msg, dict):
                error_msg = (
                    error_msg.get("title") or error_msg.get("message") or error_msg
                )
            logger.warning(
                f"Error fetching conditions for policy {policy_id}: {error_msg}"
            )
            return []

        data = response.json()
        # Handle both possible response formats
        conditions = data.get("nrql_conditions") or data.get("conditions") or []
        return conditions

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
