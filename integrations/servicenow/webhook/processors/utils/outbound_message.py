from typing import Optional, Dict, Any, Callable, Awaitable
from loguru import logger

REST_MESSAGE_NAME = "Ocean Port Outbound"


async def find_rest_message(
    make_request: Callable[..., Awaitable[Optional[Dict[str, Any]]]],
    table_base_url: str,
    name: str,
) -> Optional[str]:
    url = f"{table_base_url}/sys_rest_message"
    params = {
        "sysparm_query": f"name={name}^EQ",
        "sysparm_fields": "sys_id",
        "sysparm_limit": "1",
    }
    response = await make_request(url, params=params)
    if response and (result := response.get("result", [])):
        return result[0]["sys_id"]
    return None


async def create_rest_message_parent(
    make_request: Callable[..., Awaitable[Optional[Dict[str, Any]]]],
    table_base_url: str,
    webhook_url: str,
) -> Optional[str]:
    """Create the parent Outbound REST Message record."""
    parent_payload = {
        "name": REST_MESSAGE_NAME,
        "rest_endpoint": webhook_url,
        "description": "Sends ServiceNow records (insert/update) to Port catalog",
    }

    parent_url = f"{table_base_url}/sys_rest_message"
    logger.debug(f"Creating REST Message → {webhook_url}")

    parent_response = await make_request(
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


async def create_rest_message_function(
    make_request: Callable[..., Awaitable[Optional[Dict[str, Any]]]],
    table_base_url: str,
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

    fn_url = f"{table_base_url}/sys_rest_message_fn"
    fn_response = await make_request(fn_url, method="POST", json_data=function_payload)

    if (
        not fn_response
        or "result" not in fn_response
        or "sys_id" not in fn_response["result"]
    ):
        logger.warning(
            "Failed to create POST method - continuing anyway",
            extra={"response": fn_response},
        )


async def create_rest_message_if_not_exists(
    make_request: Callable[..., Awaitable[Optional[Dict[str, Any]]]],
    table_base_url: str,
    webhook_url: str,
) -> Optional[str]:
    """Find an existing REST Message or create a new one"""
    parent_sys_id = await find_rest_message(
        make_request, table_base_url, REST_MESSAGE_NAME
    )
    if parent_sys_id:
        logger.debug(f"Using existing REST Message → sys_id: {parent_sys_id}")
        return parent_sys_id

    parent_sys_id = await create_rest_message_parent(
        make_request, table_base_url, webhook_url
    )
    if not parent_sys_id:
        return None

    await create_rest_message_function(
        make_request, table_base_url, parent_sys_id, webhook_url
    )
    return REST_MESSAGE_NAME
