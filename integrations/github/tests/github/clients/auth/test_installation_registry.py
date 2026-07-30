import time
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github.clients.auth.github_app import installation_registry
from github.clients.auth.github_app.app_authenticator import GitHubAppAuthenticator
from github.clients.auth.github_app.installation_authenticator import (
    GitHubAppInstallationAuthenticator,
)
from port_ocean.context.ocean import ocean


@pytest.fixture(autouse=True)
def reset_registry() -> Generator[None, None, None]:
    installation_registry.reset_authenticators_by_org()
    yield
    installation_registry.reset_authenticators_by_org()


def _mock_authenticator(organization: str) -> GitHubAppInstallationAuthenticator:
    return GitHubAppInstallationAuthenticator(
        app_auth=AsyncMock(),
        organization=organization,
        installation_id="1",
    )


@pytest.mark.asyncio
async def test_list_installations_refreshes_after_ttl() -> None:
    installation_registry._authenticators_by_org["org-a"] = _mock_authenticator("org-a")
    installation_registry._discovered_at = (
        time.monotonic() - installation_registry._DISCOVERY_TTL_SECONDS - 1
    )

    with patch.object(
        installation_registry,
        "_fetch_installations",
        AsyncMock(return_value={"org-b": _mock_authenticator("org-b")}),
    ) as mock_fetch:
        authenticators = await installation_registry.list_installations_authenticators()

    mock_fetch.assert_called_once()
    assert [auth.organization for auth in authenticators] == ["org-b"]


@pytest.mark.asyncio
async def test_get_installation_authenticator_is_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(ocean.integration_config, "github_organization")

    async def iter_installations() -> AsyncGenerator[list[dict[str, object]], None]:
        yield [{"id": 1, "account": {"login": "myorg"}}]

    app_auth = MagicMock()
    app_auth.iter_app_installations = iter_installations

    with patch.object(
        GitHubAppAuthenticator,
        "from_config",
        return_value=app_auth,
    ):
        authenticator = (
            await installation_registry.get_installation_authenticator_for_organization(
                "MyOrg"
            )
        )

    assert authenticator.organization == "myorg"
