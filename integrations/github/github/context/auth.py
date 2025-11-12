import asyncio
from typing import Optional
from pydantic import BaseModel

from github.clients.client_factory import create_github_client
from port_ocean.context.ocean import ocean


class BaseAuthContext(BaseModel):
    """
    Model representing GitHub authentication data.
    """

    id: int


class AppAuthContext(BaseAuthContext):
    """
    Model representing GitHub authenticated app data.
    See: https://docs.github.com/en/rest/apps/apps?apiVersion=2022-11-28#get-the-authenticated-app
    """

    slug: str


class UserAuthContext(BaseAuthContext):
    """
    Model representing GitHub authenticated user data.
    See: https://docs.github.com/en/rest/users/users#get-the-authenticated-user
    """

    login: str


_app_auth_context: Optional[AppAuthContext] = None
_user_auth_context: Optional[UserAuthContext] = None

_auth_lock = asyncio.Lock()


async def get_authenticated_app() -> AppAuthContext:
    global _app_auth_context
    if _app_auth_context is not None:
        return _app_auth_context

    async with _auth_lock:
        client = create_github_client()
        response = await client.send_api_request(f"{client.base_url}/app")
        _app_auth_context = AppAuthContext.parse_obj(response)
        return _app_auth_context


async def get_authenticated_user() -> UserAuthContext:
    global _user_auth_context
    if _user_auth_context is not None:
        return _user_auth_context

    async with _auth_lock:
        client = create_github_client()
        response = await client.send_api_request(f"{client.base_url}/user")
        _user_auth_context = UserAuthContext.parse_obj(response)
        return _user_auth_context


async def get_authenticated_actor() -> str:
    if ocean.integration_config.get("github_app_id"):
        return f"{(await get_authenticated_app()).slug}[bot]"
    return (await get_authenticated_user()).login
