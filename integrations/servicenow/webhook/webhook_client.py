from client import ServicenowClient
from loguru import logger
from typing import List, Dict, Any, Optional
import asyncio

from webhook.events import DEFAULT_FIELDS_PER_TABLE

REST_MESSAGE_NAME = "Ocean Port Outbound"


class ServicenowWebhookClient(ServicenowClient):
    """Handles ServiceNow outbound webhook setup (REST Message + Business Rules)"""

    def _generate_business_rule_script(
        self, fields: List[str], delete_event: bool = False
    ) -> str:
        payload_lines: List[str] = []

        for field in fields:
            safe_name = field.replace(".", "_")
            source = "previous" if delete_event else "current"
            payload_lines.append(f'    "{safe_name}": {source}.{field} + "",')

        if payload_lines:
            payload_lines[-1] = payload_lines[-1].rstrip(",")

        script = f"""
            (function executeRule(current, previous) {{
            var rm = new sn_ws.RESTMessageV2('{REST_MESSAGE_NAME}', 'post');

            var payload = {{
        {chr(10).join(payload_lines)}
            }};

            rm.setRequestBody(JSON.stringify(payload));
            rm.execute();
        }})(current, previous);
        """

        return script.strip()

    def _build_upsert_rule_payload(
        self,
        rule_name: str,
        table_name: str,
        fields: List[str],
        order: int,
    ) -> Dict[str, Any]:
        """Build the payload for an `upsert event` business rule."""
        upsert_event_script = self._generate_business_rule_script(fields)
        return {
            "name": rule_name,
            "sys_scope": "global",
            "collection": table_name,
            "active": "true",
            "when": "async",
            "advanced": "true",
            "action_insert": "true",
            "action_update": "true",
            "action_delete": "false",
            "action_query": "false",
            "order": order,
            "priority": 100,
            "description": f"Forwards {table_name} create/update events to Port",
            "script": upsert_event_script,
        }

    def _build_delete_rule_payload(
        self,
        rule_name: str,
        table_name: str,
        fields: List[str],
        order: int,
    ) -> Dict[str, Any]:
        """Build the payload for a `delete event` business rule."""
        delete_event_script = self._generate_business_rule_script(
            fields, delete_event=True
        )
        return {
            "name": f"{rule_name} (delete)",
            "sys_scope": "global",
            "collection": table_name,
            "active": "true",
            "when": "after",
            "advanced": "true",
            "action_insert": "false",
            "action_update": "false",
            "action_delete": "true",
            "action_query": "false",
            "order": order,
            "priority": 100,
            "description": f"Forwards {table_name} delete events to Port",
            "script": delete_event_script,
        }

    async def _submit_business_rules(
        self,
        rule_name: str,
        payloads: List[Dict[str, Any]],
    ) -> None:
        """Submit business rule payloads to ServiceNow."""
        url = f"{self.table_base_url}/sys_script"
        logger.debug(f"Creating BR → {rule_name}")

        tasks = [
            self.make_request(url, method="POST", json_data=payload)
            for payload in payloads
        ]
        responses = await asyncio.gather(*tasks)

        for index, response in enumerate(responses):
            prefix = "Upsert" if index == 0 else "Delete"
            if response and "result" in response and "sys_id" in response["result"]:
                logger.info(f"{prefix} business rule created → {rule_name}")
            else:
                logger.error(
                    f"Failed to create {prefix} business rule {rule_name}",
                    extra={"response": response},
                )

    async def _business_rule_exists(
        self,
        name: str,
        table: str,
    ) -> bool:
        url = f"{self.table_base_url}/sys_script"
        params = {
            "sysparm_query": f"name={name}^table={table}^EQ",
            "sysparm_limit": "1",
        }
        response = await self.make_request(url, params=params)
        return bool(response and response.get("result"))

    async def _create_business_rule_if_not_exists(
        self,
        table_name: str,
        fields: List[str],
        order: int = 1000,
    ) -> None:
        """Create upsert and delete business rules for a table if they don't exist."""
        rule_name = f"Ocean Port: {table_name}"

        if await self._business_rule_exists(rule_name, table_name):
            logger.info(
                f'Business rule "{rule_name}" already exists for {table_name}. Skipping creation...'
            )
            return

        upsert_event_subscription_payload = self._build_upsert_rule_payload(
            rule_name, table_name, fields, order
        )
        delete_event_subscription_payload = self._build_delete_rule_payload(
            rule_name, table_name, fields, order
        )

        await self._submit_business_rules(
            rule_name,
            [upsert_event_subscription_payload, delete_event_subscription_payload],
        )

    async def _find_rest_message(self, name: str = REST_MESSAGE_NAME) -> Optional[str]:
        url = f"{self.table_base_url}/sys_rest_message"
        params = {
            "sysparm_query": f"name={name}^EQ",
            "sysparm_fields": "sys_id",
            "sysparm_limit": "1",
        }

        response = await self.make_request(url, params=params)
        if response and (result := response.get("result", [])):
            return result[0]["sys_id"]
        return None

    async def _create_rest_message_parent(
        self,
        webhook_url: str,
        name: str = REST_MESSAGE_NAME,
    ) -> Optional[str]:
        """Create the parent Outbound REST Message record."""
        parent_payload = {
            "name": name,
            "rest_endpoint": webhook_url,
            "description": "Sends ServiceNow records (insert/update) to Port catalog",
        }

        parent_url = f"{self.table_base_url}/sys_rest_message"
        logger.debug(f"Creating REST Message → {webhook_url}")

        parent_response = await self.make_request(
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
        return parent_sys_id

    async def _create_rest_message_function(
        self,
        parent_sys_id: str,
        webhook_url: str,
    ) -> None:
        """Create the POST function for an Outbound REST Message."""
        function_payload = {
            "rest_message": parent_sys_id,
            "name": "Send to Port",
            "function_name": "post",
            "http_method": "POST",
            "rest_endpoint": webhook_url,
            "content_type": "application/json",
        }

        fn_url = f"{self.table_base_url}/sys_rest_message_fn"
        fn_response = await self.make_request(
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

    async def _create_rest_message_if_not_exists(
        self,
        webhook_url: str,
    ) -> bool:
        """Find an existing REST Message or create a new one"""
        parent_sys_id = await self._find_rest_message()
        if parent_sys_id:
            logger.debug(f"Using existing REST Message → sys_id: {parent_sys_id}")
            return True

        parent_sys_id = await self._create_rest_message_parent(webhook_url)
        if not parent_sys_id:
            return False

        await self._create_rest_message_function(parent_sys_id, webhook_url)
        return True

    async def create_webhook(self, webhook_base_url: str, tables: List[str]) -> None:
        """Set up webhooks for the specified tables"""
        webhook_url = f"{webhook_base_url.rstrip('/')}/integration/webhook"

        rest_message_exists = await self._create_rest_message_if_not_exists(webhook_url)
        if not rest_message_exists:
            logger.error("Cannot proceed without REST Message")
            return

        tasks = []
        order = 200

        for table_name in tables:
            if table_name not in DEFAULT_FIELDS_PER_TABLE:
                logger.warning(f"Skipping unknown table: {table_name}")
                continue

            tasks.append(
                self._create_business_rule_if_not_exists(
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
