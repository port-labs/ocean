from typing import List, Dict, Any, Callable, Awaitable, Optional
import asyncio
from loguru import logger


def generate_business_rule_script(
    rest_message_name: str, fields: List[str], delete_event: bool = False
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
        var rm = new sn_ws.RESTMessageV2('{rest_message_name}', 'post');

        var payload = {{
    {chr(10).join(payload_lines)}
        }};

        rm.setRequestBody(JSON.stringify(payload));
        rm.execute();
    }})(current, previous);
    """

    return script.strip()


def build_upsert_rule_payload(
    rule_name: str,
    table_name: str,
    fields: List[str],
    order: int,
    rest_message_name: str,
) -> Dict[str, Any]:
    """Build the payload for an `upsert event` business rule."""
    upsert_event_script = generate_business_rule_script(rest_message_name, fields)
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


def build_delete_rule_payload(
    rule_name: str,
    table_name: str,
    fields: List[str],
    order: int,
    rest_message_name: str,
) -> Dict[str, Any]:
    """Build the payload for a `delete event` business rule."""
    delete_event_script = generate_business_rule_script(
        rest_message_name, fields, delete_event=True
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


async def submit_business_rules(
    make_request: Callable[..., Awaitable[Optional[Dict[str, Any]]]],
    table_base_url: str,
    rule_name: str,
    payloads: List[Dict[str, Any]],
) -> None:
    """Submit business rule payloads to ServiceNow."""
    url = f"{table_base_url}/sys_script"
    logger.debug(f"Creating BR → {rule_name}")

    tasks = [
        make_request(url, method="POST", json_data=payload) for payload in payloads
    ]
    responses = await asyncio.gather(*tasks)

    for response in responses:
        if response and "result" in response and "sys_id" in response["result"]:
            logger.info(f"Business rule created → {rule_name}")
        else:
            logger.error(
                f"Failed to create business rule {rule_name}",
                extra={"response": response},
            )


async def business_rule_exists(
    make_request: Callable[..., Awaitable[Optional[Dict[str, Any]]]],
    table_base_url: str,
    name: str,
    table: str,
) -> bool:
    url = f"{table_base_url}/sys_script"
    params = {
        "sysparm_query": f"name={name}^table={table}^EQ",
        "sysparm_limit": "1",
    }
    response = await make_request(url, params=params)
    return bool(response and response.get("result"))


async def create_business_rule_if_not_exists(
    make_request: Callable[..., Awaitable[Optional[Dict[str, Any]]]],
    table_base_url: str,
    rest_message_name: str,
    table_name: str,
    fields: List[str],
    order: int = 1000,
) -> None:
    """Create upsert and delete business rules for a table if they don't exist."""
    rule_name = f"Ocean Port: {table_name}"

    if await business_rule_exists(make_request, table_base_url, rule_name, table_name):
        logger.info(
            f'Business rule "{rule_name}" already exists for {table_name}. Skipping creation...'
        )
        return

    upsert_event_subscription_payload = build_upsert_rule_payload(
        rule_name, table_name, fields, order, rest_message_name
    )
    delete_event_subscription_payload = build_delete_rule_payload(
        rule_name, table_name, fields, order, rest_message_name
    )

    await submit_business_rules(
        make_request,
        table_base_url,
        rule_name,
        [upsert_event_subscription_payload, delete_event_subscription_payload],
    )
