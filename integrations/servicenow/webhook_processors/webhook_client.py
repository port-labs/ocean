from client import ServicenowClient
from loguru import logger
from typing import Optional, Dict, Any, List
from webhook_processors.events import DEFAULT_FIELDS_PER_TABLE
import httpx
import asyncio


class ServicenowWebhookClient(ServicenowClient):
    """Handles Servicenow Event Hooks operations."""

    async def _make_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | None:
        """Send request to ServiceNow API with error handling."""

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
            logger.error(f"HTTP occurred while fetching Servicenow data: {str(e)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {str(e)}")
        return None

    async def _outbound_rest_message_exists(self, name: str) -> Optional[str]:
        """Check if REST message already exists"""
        url = f"{self.table_base_url}/sys_rest_message_fn"
        params = {
            "sysparm_query": f"name={name}^EQ",
            "sysparm_fields": "sys_id",
            "sysparm_limit": "1",
        }

        response = await self._make_request(url, params=params)
        if not response:
            return None
        results = response.get("result", [])
        if results:
            return results[0]["sys_id"]
        return None

    async def _configure_outbound_rest_message(
        self, port_webhook_url: str
    ) -> Optional[str]:
        """Create outbound REST message"""
        rest_message_name = "Ocean Port Outbound"
        existing_id = await self._outbound_rest_message_exists(rest_message_name)
        if existing_id:
            logger.info(
                f"Using existing outbound REST message with sys_id: {existing_id}"
            )
            return existing_id

        payload = {
            "name": rest_message_name,
            "endpoint": port_webhook_url,
            "http_method": "POST",
            "content_type": "application/json",
            "description": "Sends various ServiceNow records updates/creates to Port catalog",
        }

        url = f"{self.table_base_url}/sys_rest_message_fn"
        logger.debug(f"Creating new outbound REST message for {port_webhook_url}")

        response = await self._make_request(url, method="POST", json_data=payload)

        if (
            not response
            or "result" not in response
            or "sys_id" not in response["result"]
        ):
            logger.error(
                "Failed to create outbound REST message", extra={"response": response}
            )
            return None

        rest_message_sys_id = response["result"]["sys_id"]
        logger.info(f"Outbound REST message created with sys_id: {rest_message_sys_id}")
        return rest_message_sys_id

    async def _business_rule_exists(self, name: str, table: str) -> bool:
        """Check if business rule already exists"""
        url = f"{self.table_base_url}/sys_script"
        params = {
            "sysparm_query": f"name={name}^table={table}^EQ",
            "sysparm_fields": "sys_id",
            "sysparm_limit": "1",
        }

        response = await self._make_request(url, params=params)
        if not response:
            return False
        return bool(response.get("result"))

    async def _create_business_rule_if_not_exists(
        self,
        rest_message_sys_id: str,
        table_name: str,
        fields: List[str],
        order: int = 100,
    ) -> None:
        """Create async Business Rule for any table

        Args:
            rest_message_sys_id: The sys_id of the outbound REST message
            table_name: The name of the table to create the business rule for
            fields: The fields to include in the business rule
            order: The order of the business rule
        """
        rule_name = f"Ocean Port - {table_name} - Webhook"
        if await self._business_rule_exists(rule_name, table_name):
            logger.info(
                f"Business rule {rule_name} already exists for table {table_name}"
            )
            return

        payload_lines: List[str] = []
        for field in fields:
            payload_lines.append(f"    {field}: current.{field} + '',")

        payload_str = "\n".join(payload_lines)

        script = f"""
        (function executeRule(current, previous) {{
            var rm = new sn_ws.RESTMessageV2('{rest_message_sys_id}', 'default');

            var payload = {{
                {payload_str}
                sys_updated_on: current.sys_updated_on + '',
                sys_updated_by: current.sys_updated_by + ''
            }};

            rm.setRequestBody(JSON.stringify(payload));
            rm.execute();
        }})(current, previous);
        """

        payload = {
            "name": rule_name,
            "sys_scope": "global",
            "table": table_name,
            "active": True,
            "when": "async",
            "insert": True,
            "update": True,
            "delete": False,
            "query": False,
            "advanced": True,
            "order": order,
            "description": f"Forwards {table_name} events to Port catalog",
            "script": script.strip(),
        }

        url = f"{self.table_base_url}/sys_script"
        logger.debug(f"Creating Business Rule: {rule_name} with payload: {payload}")

        response = await self._make_request(url, method="POST", json_data=payload)

        success = bool(
            response and "result" in response and "sys_id" in response["result"]
        )
        if success:
            logger.info("Business Rule created successfully")
        else:
            logger.error("Failed to create Business Rule", extra={"response": response})

    async def create_webhook(self, webhook_base_url: str, tables: List[str]) -> None:
        """Create a webhook for supported tables."""
        webhook_url = f"{webhook_base_url.rstrip('/')}/integration/webhook"
        rest_id = await self._configure_outbound_rest_message(webhook_url)
        if not rest_id:
            logger.error("Failed to create outbound REST message")
            return

        tasks = []
        for table_name in tables:
            if table_name not in DEFAULT_FIELDS_PER_TABLE:
                logger.warning(
                    f"Table {table_name} not found in DEFAULT_FIELDS_PER_TABLE"
                )
                continue
            tasks.append(
                self._create_business_rule_if_not_exists(
                    rest_id,
                    table_name,
                    DEFAULT_FIELDS_PER_TABLE[table_name],
                )
            )

        if tasks:
            await asyncio.gather(*tasks)
            logger.success(f"Webhook setup completed for {len(tasks)} tables")
