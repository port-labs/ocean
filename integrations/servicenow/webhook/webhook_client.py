from client import ServicenowClient
from loguru import logger
from typing import List
import asyncio

from webhook.events import DEFAULT_FIELDS_PER_TABLE
from webhook.processors.utils.outbound_message import create_rest_message_if_not_exists
from webhook.processors.utils.business_rule import create_business_rule_if_not_exists


class ServicenowWebhookClient(ServicenowClient):
    """Handles ServiceNow outbound webhook setup (REST Message + Business Rules)"""

    async def create_webhook(self, webhook_base_url: str, tables: List[str]) -> None:
        """Set up webhooks for the specified tables"""
        webhook_url = f"{webhook_base_url.rstrip('/')}/integration/webhook"

        rest_message_name = await create_rest_message_if_not_exists(
            self.make_request, self.table_base_url, webhook_url
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
                    self.make_request,
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
