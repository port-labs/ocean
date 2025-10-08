from typing import Dict, Any, Optional

from pydantic import BaseModel
from werkzeug.local import LocalProxy

from integrations.github.github.clients.client_factory import create_github_client
from integrations.github.github.clients.http.rest_client import GithubRestClient


class AuthContext(BaseModel):
    """
    Model representing GitHub authenticated user data.
    See: https://docs.github.com/en/rest/users/users#get-the-authenticated-user
    """

    login: str
    id: int
    name: str
    email: str


_context: AuthContext | None = None


async def _get_context() -> AuthContext:
    global _context
    if _context is not None:
        return _context

    client = create_github_client()
    response = await client.send_api_request(f"{client.base_url}/user")
    _context = AuthContext.parse_obj(response)

    return _context


authenticated_user: AuthContext = LocalProxy(lambda: _get_context())  # type: ignore
