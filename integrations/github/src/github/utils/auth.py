from typing import Optional

from .exceptions import TokenNotFoundException, UserAgentNotFoundException


class AuthClient:
    def __init__(
            self,
            access_token: Optional[str] = None,
            user_agent: Optional[str] = None,
    ):
        # access token config setup
        if access_token is None:
            raise TokenNotFoundException("Provide valid GitHub personal access token")
        self._token = access_token

        # user agent config setup
        if user_agent is None:
            raise UserAgentNotFoundException(
                "Provide valid GitHub username as User-Agent"
            )
        self._user_agent = user_agent

        # configure headers for an http client
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": f"{self._user_agent}",
        }

    def get_headers(self) -> dict[str, str]:
        return self._headers

    def get_user_agent(self) -> str:
        return self._user_agent
