from client import ServicenowClient
from loguru import logger
from port_ocean.context.ocean import ocean
from typing import List, Dict, Any, Optional
import asyncio

from webhook.events import DEFAULT_FIELDS_PER_TABLE

REST_MESSAGE_NAME = "Ocean Port Webhook"
WEBHOOK_ENDPOINT = "/webhook"
AUTHORIZATION_HEADER_NAME = "Authorization"
WEBHOOK_SECRET_CONFIG_KEY = "webhook_secret"


class ServicenowWebhookClient(ServicenowClient):
    """Handles ServiceNow outbound webhook setup (REST Message + Business Rules)"""

    def _generate_business_rule_script(
        self, table_name: str, fields: List[str], delete_event: bool = False
    ) -> str:
        source = "previous" if delete_event else "current"
        payload_lines: List[str] = [f'    "__table_name": "{table_name}",']

        for field in fields:
            safe_name = field.replace(".", "_")
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
        upsert_event_script = self._generate_business_rule_script(table_name, fields)
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
            table_name, fields, delete_event=True
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
            if response and response.json().get("result", {}):
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
        return bool(response and response.json().get("result", {}))

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
        if not response:
            return None
        if result := response.json().get("result", []):
            try:
                return result[0]["sys_id"]
            except (IndexError, KeyError):
                logger.warning(
                    f"Unexpected REST Message response for {name}",
                    extra={"result": result},
                )
                return None
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
        if not parent_response:
            return None
        result = parent_response.json().get("result", {})
        if not (result and "sys_id" in result):
            logger.error(
                "Failed to create REST Message", extra={"response": parent_response}
            )
            return None

        parent_sys_id = result["sys_id"]
        logger.info(f"REST Message created → sys_id: {parent_sys_id}")
        return parent_sys_id

    async def _create_rest_message_function(
        self,
        parent_sys_id: str,
        webhook_url: str,
    ) -> Optional[str]:
        """Create the POST function for an Outbound REST Message."""
        function_payload = {
            "rest_message": parent_sys_id,
            "name": "Send to Port",
            "function_name": "post",
            "http_method": "POST",
            "rest_endpoint": webhook_url,
            "content_type": "application/json",
        }

        function_url = f"{self.table_base_url}/sys_rest_message_fn"
        function_response = await self.make_request(
            function_url, method="POST", json_data=function_payload
        )
        if not function_response:
            return None

        result = function_response.json().get("result", {})
        if result and "sys_id" in result:
            function_sys_id = result["sys_id"]
            logger.info(f"REST Message function created → sys_id: {function_sys_id}")
            return function_sys_id
        else:
            logger.error(
                f"Failed to create 'post' HTTP Method for '{REST_MESSAGE_NAME}' REST Message. Aborting setup...",
                extra={"response": function_response},
            )
            return None

    async def _create_rest_message_if_not_exists(
        self,
        webhook_url: str,
    ) -> Optional[str]:
        """Find or create the REST Message and verify its POST function exists. Returns the parent sys_id on success."""
        parent_sys_id = await self._find_rest_message()
        if parent_sys_id:
            logger.debug(f"Using existing REST Message → sys_id: {parent_sys_id}")
            if not await self._find_rest_message_function(parent_sys_id):
                logger.warning(
                    f"REST Message function missing for {parent_sys_id}, recreating"
                )
                if not await self._create_rest_message_function(
                    parent_sys_id, webhook_url
                ):
                    return None
            return parent_sys_id

        parent_sys_id = await self._create_rest_message_parent(webhook_url)
        if not parent_sys_id:
            logger.warning(
                "REST Message parent creation failed, aborting webhook setup"
            )
            return None

        if not await self._create_rest_message_function(parent_sys_id, webhook_url):
            return None
        return parent_sys_id

    async def _find_rest_message_function(self, parent_sys_id: str) -> Optional[str]:
        """Find the POST function sys_id for a REST Message."""
        url = f"{self.table_base_url}/sys_rest_message_fn"
        params = {
            "sysparm_query": f"rest_message={parent_sys_id}^function_name=post^EQ",
            "sysparm_fields": "sys_id",
            "sysparm_limit": "1",
        }
        response = await self.make_request(url, params=params)
        if not response:
            logger.warning(
                f"Failed to retrieve REST Message function for parent {parent_sys_id}"
            )
            return None
        if result := response.json().get("result", []):
            try:
                return result[0]["sys_id"]
            except (IndexError, KeyError):
                logger.warning(
                    f"Unexpected REST Message function response for parent {parent_sys_id}",
                    extra={"result": result},
                )
                return None
        logger.debug(f"No REST Message function found for parent {parent_sys_id}")
        return None

    async def _get_existing_auth_header(self, function_sys_id: str) -> Optional[str]:
        """Find an existing Authorization header on a REST Message function. Returns the header sys_id if found."""
        url = f"{self.table_base_url}/sys_rest_message_fn_headers"
        params = {
            "sysparm_query": f"rest_message_function={function_sys_id}^name={AUTHORIZATION_HEADER_NAME}^EQ",
            "sysparm_fields": "sys_id",
            "sysparm_limit": "1",
        }
        response = await self.make_request(url, params=params)
        if not response:
            logger.warning(
                f"Failed to retrieve auth header for function {function_sys_id}"
            )
            return None
        if result := response.json().get("result", []):
            try:
                return result[0]["sys_id"]
            except (IndexError, KeyError):
                logger.warning(
                    f"Unexpected auth header response for function {function_sys_id}",
                    extra={"result": result},
                )
                return None
        logger.debug(f"No existing auth header found for function {function_sys_id}")
        return None

    async def _upsert_webhook_auth_header(
        self, parent_sys_id: str, webhook_secret: str
    ) -> bool:
        """Create or update the Authorization header on the REST Message function."""
        function_sys_id = await self._find_rest_message_function(parent_sys_id)
        if not function_sys_id:
            logger.warning(
                "Cannot upsert auth header — REST Message function not found"
            )
            return False
        existing_header_sys_id = await self._get_existing_auth_header(function_sys_id)

        if not existing_header_sys_id:
            url = f"{self.table_base_url}/sys_rest_message_fn_headers"
            payload = {
                "rest_message_function": function_sys_id,
                "name": AUTHORIZATION_HEADER_NAME,
                "value": webhook_secret,
            }
            response = await self.make_request(url, method="POST", json_data=payload)
            if response and response.json().get("result", {}).get("sys_id"):
                logger.info(
                    f"Authorization header created on REST Message function {function_sys_id}"
                )
                return True
            logger.error(
                f"Failed to create Authorization header on REST Message function {function_sys_id}"
            )
            return False

        url = f"{self.table_base_url}/sys_rest_message_fn_headers/{existing_header_sys_id}"
        payload = {"value": webhook_secret}
        response = await self.make_request(url, method="PATCH", json_data=payload)
        if response:
            logger.info(
                f"Authorization header updated on REST Message function {function_sys_id}"
            )
            return True
        logger.error(
            f"Failed to update Authorization header on REST Message function {function_sys_id}"
        )
        return False

    async def create_webhook(self, webhook_base_url: str, tables: List[str]) -> None:
        """Set up webhooks for the specified tables"""
        webhook_url = f"{webhook_base_url.rstrip('/')}/integration{WEBHOOK_ENDPOINT}"

        parent_sys_id = await self._create_rest_message_if_not_exists(webhook_url)
        if not parent_sys_id:
            logger.error(
                "Webhook setup failed — could not find or create REST Message and its POST function in ServiceNow"
            )
            return

        webhook_secret = ocean.integration_config.get(WEBHOOK_SECRET_CONFIG_KEY)
        if webhook_secret:
            if not await self._upsert_webhook_auth_header(
                parent_sys_id, webhook_secret
            ):
                logger.error("Aborting webhook setup, auth header configuration failed")
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
            order += 10

        if tasks:
            await asyncio.gather(*tasks)
            logger.success(f"Webhook configuration completed for {len(tasks)} tables")
        else:
            logger.info("No tables to configure")
