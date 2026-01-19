from client import ServicenowClient
from loguru import logger
from typing import Optional, Dict, Any, List
from webhook_processors.events import DEFAULT_FIELDS_PER_TABLE
import httpx
import asyncio


class ServicenowWebhookClient(ServicenowClient):
    """Handles ServiceNow outbound webhook setup (REST Message + Business Rules)"""

    REST_MESSAGE_NAME = "Ocean Port Outbound"

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
            logger.error(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
        return None

    async def _find_rest_message(self, name: str) -> Optional[str]:
        url = f"{self.table_base_url}/sys_rest_message"
        params = {
            "sysparm_query": f"name={name}^EQ",
            "sysparm_fields": "sys_id",
            "sysparm_limit": "1",
        }
        response = await self._make_request(url, params=params)
        if response and (result := response.get("result", [])):
            return result[0]["sys_id"]
        return None

    async def _create_or_get_rest_message(self, webhook_url: str) -> Optional[str]:
        parent_sys_id = await self._find_rest_message(self.REST_MESSAGE_NAME)
        if parent_sys_id:
            logger.debug(f"Using existing REST Message → sys_id: {parent_sys_id}")
            return parent_sys_id

        parent_payload = {
            "name": self.REST_MESSAGE_NAME,
            "rest_endpoint": webhook_url,
            "description": "Sends ServiceNow records (insert/update) to Port catalog",
        }

        parent_url = f"{self.table_base_url}/sys_rest_message"
        logger.debug(f"Creating REST Message → {webhook_url}")

        parent_response = await self._make_request(
            parent_url, method="POST", json_data=parent_payload
        )
        if (
            not parent_response
            or "result" not in parent_response
            or "sys_id" not in parent_response["result"]
        ):
            logger.error(
                "Failed to create REST Message", extra={"response": parent_response}
            )
            return None

        parent_sys_id = parent_response["result"]["sys_id"]
        logger.debug(f"REST Message created → sys_id: {parent_sys_id}")

        function_payload = {
            "rest_message": parent_sys_id,
            "name": "Send to Port",
            "function_name": "post",
            "http_method": "POST",
            "rest_endpoint": webhook_url,
            "content_type": "application/json",
        }

        fn_url = f"{self.table_base_url}/sys_rest_message_fn"
        fn_response = await self._make_request(
            fn_url, method="POST", json_data=function_payload
        )

        if (
            not fn_response
            or "result" not in fn_response
            or "sys_id" not in fn_response["result"]
        ):
            logger.warning(
                "Failed to create POST method - continuing anyway",
                extra={"response": fn_response},
            )

        return parent_sys_id

    async def _business_rule_exists(self, name: str, table: str) -> bool:
        url = f"{self.table_base_url}/sys_script"
        params = {
            "sysparm_query": f"name={name}^table={table}^EQ",
            "sysparm_limit": "1",
        }
        response = await self._make_request(url, params=params)
        return bool(response and response.get("result"))

    async def _create_business_rule_if_not_exists(
        self,
        rest_message_sys_id: str,
        table_name: str,
        fields: List[str],
        order: int = 1000,
    ) -> None:
        rule_name = f"Ocean {table_name} to Port webhook"

        if await self._business_rule_exists(rule_name, table_name):
            logger.debug(
                f'Business Rule "{rule_name}" already exists for {table_name}. Skipping.'
            )
            return

        payload_lines = [
            f"    {field.replace('.', '_')}: current.{field} + ''," for field in fields
        ]

        script = f"""
        (function executeRule(current, previous) {{
            var rm = new sn_ws.RESTMessageV2('{rest_message_sys_id}', 'post');

            var payload = {{
                {chr(10).join(payload_lines)}
                sys_class_name: current.sys_class_name + '',
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
            "description": f"Forwards {table_name} create/update events to Port",
            "script": script.strip(),
        }

        url = f"{self.table_base_url}/sys_script"
        logger.debug(f"Creating BR → {rule_name}")

        response = await self._make_request(url, method="POST", json_data=payload)

        if response and "result" in response and "sys_id" in response["result"]:
            logger.info(f"Business Rule created → {rule_name}")
        else:
            logger.error(
                f"Failed to create BR {rule_name}", extra={"response": response}
            )

    async def create_webhook(self, webhook_base_url: str, tables: List[str]) -> None:
        """Set up webhooks for the specified tables"""
        webhook_url = f"{webhook_base_url.rstrip('/')}/integration/webhook"

        rest_message_id = await self._create_or_get_rest_message(webhook_url)
        if not rest_message_id:
            logger.error("Cannot proceed without REST Message")
            return

        tasks = []
        order = 1000

        for table_name in tables:
            if table_name not in DEFAULT_FIELDS_PER_TABLE:
                logger.warning(f"Skipping unknown table: {table_name}")
                continue

            tasks.append(
                self._create_business_rule_if_not_exists(
                    rest_message_id,
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
