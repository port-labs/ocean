"""Handler for retrieving and filtering Harbor users."""

from typing import List, Dict, Any, AsyncGenerator

from ..client import HarborClient
from ..core.models import HarborUser


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
            yield batch_entities


def _map_user_to_entity(user: HarborUser) -> Dict[str, Any]:
    """
    Map a HarborUser to a generic Entity.
    Args:
        user (HarborUser): The Harbor user to map.
    Returns:
        Entity: The mapped entity.
    """

    return {
        "userId": user.user_id,
        "username": user.username,
        "email": user.email,
        "realname": user.realname,
        "creationTime": user.creation_time.isoformat() if user.creation_time else None,
        "updateTime": user.update_time.isoformat() if user.update_time else None,
        "sysadmin": user.sysadmin_flag,
        "adminRole": user.admin_role,
    }
