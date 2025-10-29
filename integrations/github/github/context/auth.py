import asyncio
from typing import Optional
from pydantic import BaseModel

from github.clients.client_factory import create_github_client


class AuthContext(BaseModel):
    """
    Model representing GitHub authenticated user data.
    See: https://docs.github.com/en/rest/users/users#get-the-authenticated-user
    """

    login: str
    id: int


_auth_context: Optional[AuthContext] = None
_auth_lock = asyncio.Lock()


async def get_authenticated_user() -> AuthContext:
    global _auth_context
    if _auth_context is not None:
        return _auth_context

    async with _auth_lock:
        client = create_github_client()
        response = await client.send_api_request(f"{client.base_url}/user")
        _auth_context = AuthContext.parse_obj(response)
        return _auth_context
