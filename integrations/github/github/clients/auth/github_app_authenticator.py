import asyncio
import base64
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional, cast

import jwt
from loguru import logger
from port_ocean.context.event import event

from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
    AuthScope,
    GitHubHeaders,
    GitHubToken,
)
from github.helpers.exceptions import AuthenticationException

if TYPE_CHECKING:
    from integration import GithubPortAppConfig

_scopes_by_org: dict[str, AuthScope] | None = None


def reset_installation_index() -> None:
    global _scopes_by_org
    _scopes_by_org = None


class GitHubAppAuthenticator(AbstractGitHubAuthenticator):
    JWT_EXPIRY_MINUTES = 10
    INSTALLATIONS_PAGE_SIZE = 100

    def __init__(
        self,
        app_id: str,
        private_key: str,
        organization: Optional[str],
        github_host: str,
        installation_id: Optional[str] = None,
    ):
        self.app_id = app_id
        self.installation_id = installation_id
        self.private_key = private_key
        self.organization = organization
        self.github_host = github_host.rstrip("/")
        self.cached_installation_token: Optional[GitHubToken] = None
        self.installation_token_lock = asyncio.Lock()

    @property
    def rate_limit_scope(self) -> str:
        if self.installation_id:
            return f"installation:{self.installation_id}"
        if self.organization:
            return f"org:{self.organization}"
        return "app"

    @classmethod
    def _make(
        cls,
        config: dict[str, Any],
        *,
        organization: Optional[str] = None,
        installation_id: Optional[str] = None,
    ) -> "GitHubAppAuthenticator":
        return cls(
            app_id=config["github_app_id"],
            private_key=config["github_app_private_key"],
            organization=(
                organization
                if organization is not None
                else config.get("github_organization")
            ),
            github_host=config["github_host"],
            installation_id=(
                installation_id
                if installation_id is not None
                else config.get("github_app_installation_id")
            ),
        )

    @classmethod
    def _allowed_organizations(cls) -> list[str]:
        try:
            port_app_config = cast("GithubPortAppConfig", event.port_app_config)
            return port_app_config.organizations or []
        except Exception:
            return []

    @classmethod
    def _is_allowed_org(
        cls, config: dict[str, Any], login: str, allowed: list[str]
    ) -> bool:
        if config.get("github_organization") and login != config["github_organization"]:
            return False
        if allowed and login not in allowed:
            return False
        return True

    @classmethod
    def _scope_from_installation(
        cls, config: dict[str, Any], installation: dict[str, Any]
    ) -> AuthScope:
        account = installation["account"]
        login = account["login"]
        installation_id = str(installation["id"])
        return AuthScope(
            organization=login,
            account_type=account.get("type"),
            installation_id=installation_id,
            authenticator=cls._make(
                config, organization=login, installation_id=installation_id
            ),
        )

    @classmethod
    async def _ensure_index(cls, config: dict[str, Any]) -> dict[str, AuthScope]:
        global _scopes_by_org
        if _scopes_by_org is not None:
            return _scopes_by_org

        installation_id = config.get("github_app_installation_id")
        if installation_id:
            organization = config.get("github_organization")
            account_type = None
            if not organization:
                bootstrap = cls._make(config, installation_id=installation_id)
                installation = await bootstrap.fetch_installation(installation_id)
                account = installation.get("account") or {}
                organization = account.get("login")
                account_type = account.get("type")
                if not organization:
                    raise AuthenticationException(
                        "GitHub App installation has no account login"
                    )
            scope = AuthScope(
                organization=organization,
                account_type=account_type,
                installation_id=str(installation_id),
                authenticator=cls._make(
                    config, organization=organization, installation_id=installation_id
                ),
            )
            _scopes_by_org = {(organization or ""): scope}
            return _scopes_by_org

        bootstrap = cls._make(config)
        allowed_orgs = cls._allowed_organizations()
        index: dict[str, AuthScope] = {}

        async for page in bootstrap.iter_app_installations():
            for installation in page:
                account = installation.get("account") or {}
                login = account.get("login")
                if not login or not cls._is_allowed_org(config, login, allowed_orgs):
                    continue
                index[login] = cls._scope_from_installation(config, installation)

        _scopes_by_org = index
        return _scopes_by_org

    @classmethod
    async def list_scopes(cls, config: dict[str, Any]) -> list[AuthScope]:
        scopes = list((await cls._ensure_index(config)).values())
        if not scopes:
            raise AuthenticationException("No GitHub App installations found")
        logger.info(f"Discovered {len(scopes)} GitHub App installation(s)")
        return scopes

    @classmethod
    def for_org(
        cls, config: dict[str, Any], organization: str | None
    ) -> "GitHubAppAuthenticator":
        if organization is None:
            return cls._make(config)

        if _scopes_by_org and organization in _scopes_by_org:
            return cast(
                GitHubAppAuthenticator,
                _scopes_by_org[organization].authenticator,
            )

        installation_id = config.get("github_app_installation_id")
        if installation_id and (
            not config.get("github_organization")
            or config["github_organization"] == organization
        ):
            return cls._make(
                config, organization=organization, installation_id=installation_id
            )

        return cls._make(config, organization=organization, installation_id=None)

    async def get_token(self, **kwargs: Any) -> GitHubToken:
        jwt_token = self._generate_jwt()
        if kwargs.get("return_jwt", False):
            return jwt_token

        async with self.installation_token_lock:
            if (
                self.cached_installation_token
                and not self.cached_installation_token.is_expired
            ):
                return self.cached_installation_token

            if not self.installation_id:
                if not self.organization:
                    raise AuthenticationException(
                        "Installation ID or organization is required for GitHub App auth"
                    )
                self.installation_id = await self._fetch_installation_id(
                    jwt_token.token
                )

            self.cached_installation_token = await self._fetch_installation_token(
                jwt_token.token
            )
            logger.info("New GitHub App token acquired.")
            return self.cached_installation_token

    async def get_headers(self, **kwargs: Any) -> GitHubHeaders:
        token_response = await self.get_token(**kwargs)
        return GitHubHeaders(
            Authorization=f"Bearer {token_response.token}",
            Accept="application/vnd.github+json",
            X_GitHub_Api_Version="2022-11-28",
        )

    def _parse_next_link(self, link_header: str) -> Optional[str]:
        for part in link_header.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                url_part = part.split(";")[0].strip()
                return url_part.strip("<>")
        return None

    async def fetch_installation(
        self, installation_id: Optional[str] = None
    ) -> dict[str, Any]:
        resolved_id = installation_id or self.installation_id
        if not resolved_id:
            raise AuthenticationException("Installation ID is required")

        jwt_token = await self.get_token(return_jwt=True)
        url = f"{self.github_host}/app/installations/{resolved_id}"
        response = await self.client.get(
            url,
            headers={
                "Authorization": f"Bearer {jwt_token.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response.raise_for_status()
        return response.json()

    async def iter_app_installations(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        jwt_token = await self.get_token(return_jwt=True)
        headers = {
            "Authorization": f"Bearer {jwt_token.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url: Optional[str] = f"{self.github_host}/app/installations"

        while url:
            response = await self.client.get(
                url,
                params={"per_page": self.INSTALLATIONS_PAGE_SIZE},
                headers=headers,
            )
            response.raise_for_status()
            page: list[dict[str, Any]] = response.json()
            if page:
                yield page
            link_header = response.headers.get("Link", "")
            url = self._parse_next_link(link_header)

    async def _fetch_installation_id(self, jwt_token: str) -> str:
        try:
            url = f"{self.github_host}/users/{self.organization}/installation"
            headers = {"Authorization": f"Bearer {jwt_token}"}
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return str(response.json()["id"])
        except Exception as e:
            raise AuthenticationException(
                f"Failed to fetch installation ID: {e}"
            ) from e

    async def _fetch_installation_token(self, jwt_token: str) -> GitHubToken:
        try:
            url = f"{self.github_host}/app/installations/{self.installation_id}/access_tokens"
            headers = {"Authorization": f"Bearer {jwt_token}"}
            response = await self.client.post(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return GitHubToken(token=data["token"], expires_at=data["expires_at"])
        except Exception as e:
            raise AuthenticationException(
                f"Failed to fetch installation token: {e}"
            ) from e

    def _generate_jwt(self) -> GitHubToken:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.JWT_EXPIRY_MINUTES)
        payload = {
            "iss": self.app_id,
            "iat": now,
            "exp": expires_at,
        }
        if self.private_key.startswith("-----BEGIN"):
            decoded_private_key = self.private_key
        else:
            decoded_private_key = base64.b64decode(self.private_key).decode()

        token = jwt.encode(payload, decoded_private_key, algorithm="RS256")
        return GitHubToken(token=token, expires_at=str(int(expires_at.timestamp())))
