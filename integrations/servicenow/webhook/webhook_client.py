from client import ServicenowClient
from loguru import logger
from typing import Optional, Dict, Any, List
import httpx
import asyncio

from webhook.events import DEFAULT_FIELDS_PER_TABLE
from webhook.processors.utils.outbound_message import create_rest_message_if_not_exists
from webhook.processors.utils.business_rule import create_business_rule_if_not_exists


class ServicenowWebhookClient(ServicenowClient):
    """Handles ServiceNow outbound webhook setup (REST Message + Business Rules)"""

    async def _make_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        await self._ensure_auth_headers()
        try:
            response = await self.http_client.request(
                url=resource,
                params=params,
                method=method,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
        except httpx.HTTPError as e:
            logger.error(
                f"HTTP error occurred while fetching Servicenow data: {str(e)}"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error occurred while fetching Servicenow data: {str(e)}"
            )
        return None

    async def create_webhook(self, webhook_base_url: str, tables: List[str]) -> None:
        """Set up webhooks for the specified tables"""
        webhook_url = f"{webhook_base_url.rstrip('/')}/integration/webhook"

        rest_message_name = await create_rest_message_if_not_exists(
            self._make_request, self.table_base_url, webhook_url
        )
        if not rest_message_name:
            logger.error("Cannot proceed without REST Message")
            return

        tasks = []
        order = 200

        for table_name in tables:
            if table_name not in DEFAULT_FIELDS_PER_TABLE:
                logger.warning(f"Skipping unknown table: {table_name}")
                continue

            tasks.append(
                create_business_rule_if_not_exists(
                    self._make_request,
                    self.table_base_url,
                    rest_message_name,
                    table_name,
                    DEFAULT_FIELDS_PER_TABLE[table_name],
                    order=order,
                )
            )
            order += 10  # prevent order collisions

        if tasks:
            await asyncio.gather(*tasks)
            logger.success(f"Webhook configuration completed for {len(tasks)} tables")
        else:
            logger.info("No valid tables to configure")

    async def get_record_by_sys_id(
        self, table_name: str, sys_id: str
    ) -> Optional[dict[str, Any]]:
        url = f"{self.table_base_url}/{table_name}/{sys_id}"
        response = await self._make_request(url)
        if response and (result := response.get("result", {})):
            return result
        return None
