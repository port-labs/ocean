"""Handler for retrieving and filtering Harbor users."""

from typing import List, Dict, Any, AsyncGenerator

from ..client import HarborClient
from ..core.models import HarborUser

from ..core.logger import logger


async def get_users(client: HarborClient) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Retrieve and filter Harbor users based on configuration.
    Args:
        client (HarborClient): Harbor API client.
    Returns:
        AsyncGenerator[List[Dict[str, Any], None]
    """

    async for user_batch in client.get_users():
        batch_entities = []
        for user_data in user_batch:
            user = HarborUser(**user_data)
            entity_dict = _map_user_to_entity(user)
            batch_entities.append(entity_dict)

        if batch_entities:
            logger.debug("user_batch: {}", batch_entities)
            yield batch_entities


def _map_user_to_entity(user: HarborUser) -> Dict[str, Any]:
    """
    Map a HarborUser to a generic Entity.
    Args:
        user (HarborUser): The Harbor user to map.
    Returns:
        Entity: The mapped entity.
    """
    logger.debug("Mapping user to entity: {}", user)

    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "realname": user.realname,
        "creation_time": user.creation_time.isoformat() if user.creation_time else None,
        "update_time": user.update_time.isoformat() if user.update_time else None,
        "sysadmin_flag": user.sysadmin_flag,
        "admin_role_in_auth": user.admin_role_in_auth,
        "comment": user.comment,
    }
