from enum import StrEnum
from typing import Any
from hibob.client import HiBobClient
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import RAW_RESULT


class ObjectKind(StrEnum):
    PROFILE = "profile"
    LIST = "list"


@ocean.on_resync(ObjectKind.PROFILE)
async def resync_profile(kind: str) -> RAW_RESULT:
    client = HiBobClient(
        ocean.integration_config["hibob_api_url"],
        ocean.integration_config["hibob_username"],
        ocean.integration_config["hibob_password"],
    )
    profiles = await client.get_profiles()
    logger.info(f"Fetched {len(profiles)} profiles")
    return profiles


@ocean.on_resync(ObjectKind.LIST)
async def resync_list(kind: str) -> RAW_RESULT:
    client = HiBobClient(
        ocean.integration_config["hibob_api_url"],
        ocean.integration_config["hibob_username"],
        ocean.integration_config["hibob_password"],
    )
    company_lists = await client.get_all_lists()
    logger.info(f"Fetched {len(company_lists)} lists")
    return transform_to_array_of_lists(company_lists)


def transform_to_array_of_lists(lists_object: dict[str, Any]) -> list[dict[str, Any]]:
    array_of_lists = []
    for list_name, list_content in lists_object.items():
        transformed_entry = {
            "name": list_name,
            "values": list_content.get("values", []),
            "items": list_content.get("items", []),
        }
        array_of_lists.append(transformed_entry)
    return array_of_lists
