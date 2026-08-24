from typing import Iterator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from port_ocean.identity_propagation.vault.base import TokenRecord, VaultClient
from port_ocean.exceptions.identity_propagation import (
    IdentityVerifierNotAvailableError,
    IdentityVerificationError,
    OAuthError,
    OAuthProviderNotConfiguredError,
    VaultError,
)
from port_ocean.identity_propagation.oauth_broker import router as router_module
from port_ocean.identity_propagation.oauth_broker import state as state_module
from port_ocean.identity_propagation.oauth_broker.router import register_oauth_broker
from port_ocean.identity_propagation.oauth_broker.state import sign_state

AUTHORIZE_PARAMS = {
    "runId": "run_1",
    "nodeRunId": "wfnr_1",
    "actorId": "jane@acme.com",
    "orgId": "org_1",
}


@pytest.fixture
def mock_vault() -> MagicMock:
    vault = MagicMock(spec=VaultClient)
    vault.write = AsyncMock()
    return vault


@pytest.fixture
def mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.target = "github-ocean"
    provider.authorization_url = MagicMock(
        return_value="https://github.com/login/oauth/authorize?client_id=x"
    )
    provider.exchange_code = AsyncMock(
        return_value=TokenRecord(access_token="gho_token")
    )
    return provider


@pytest.fixture
def mock_verifier() -> MagicMock:
    verifier = MagicMock()
    verifier.verify_run_actor = AsyncMock(return_value="org_1")
    return verifier


@pytest.fixture
def mock_http_client() -> MagicMock:
    mock = MagicMock()
    mock.post = AsyncMock(
        return_value=MagicMock(spec=httpx.Response, status_code=200)
    )
    return mock


@pytest.fixture
def mock_ocean(
    mock_vault: MagicMock,
    mock_verifier: MagicMock,
) -> MagicMock:
    mock = MagicMock()
    mock.app.base_url = "https://ocean.acme.com"
    mock.app.route_prefix = ""
    mock.app.vault_client = mock_vault
    mock.app.identity_verifier = mock_verifier
    mock.port_client.api_url = "https://api.getport.io/v1"
    mock.port_client.auth.headers = AsyncMock(return_value={"Authorization": "Bearer token"})
    mock.config.port.client_secret = "test-client-secret"
    mock.config.port.app_url = None  # exercise the api_url-derived fallback
    mock.config.identity_propagation.oauth.state_signing_secret = None
    return mock


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    mock_ocean: MagicMock,
    mock_provider: MagicMock,
    mock_http_client: MagicMock,
) -> Iterator[TestClient]:
    app = FastAPI()
    mock_ocean.app.fast_api_app = app

    monkeypatch.setattr(router_module, "ocean", mock_ocean)
    monkeypatch.setattr(state_module, "ocean", mock_ocean)
    monkeypatch.setattr(router_module, "require_provider", lambda: mock_provider)
    monkeypatch.setattr(router_module, "http_async_client", mock_http_client)

    register_oauth_broker()

    with TestClient(app) as test_client:
        yield test_client


def test_authorize_redirects_to_the_provider(
    client: TestClient, mock_provider: MagicMock
) -> None:
    response = client.get(
        "/v1/oauth-broker/authorize", params=AUTHORIZE_PARAMS, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"].startswith("https://github.com/login/oauth")
    redirect_uri, _ = mock_provider.authorization_url.call_args.args
    assert redirect_uri == "https://ocean.acme.com/v1/oauth-broker/callback"


def test_authorize_rejects_an_unconfigured_target(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, mock_verifier: MagicMock
) -> None:
    monkeypatch.setattr(
        router_module,
        "require_provider",
        lambda: (_ for _ in ()).throw(OAuthProviderNotConfiguredError("not found")),
    )

    response = client.get(
        "/v1/oauth-broker/authorize", params=AUTHORIZE_PARAMS, follow_redirects=False
    )

    assert response.status_code == 404
    mock_verifier.verify_run_actor.assert_not_called()


def test_authorize_rejects_an_actor_who_does_not_own_the_run(
    client: TestClient, mock_verifier: MagicMock
) -> None:
    mock_verifier.verify_run_actor.side_effect = IdentityVerificationError(
        "actor mismatch"
    )

    response = client.get(
        "/v1/oauth-broker/authorize", params=AUTHORIZE_PARAMS, follow_redirects=False
    )

    assert response.status_code == 403


def test_authorize_is_unavailable_while_verification_is_stubbed(
    client: TestClient, mock_verifier: MagicMock
) -> None:
    mock_verifier.verify_run_actor.side_effect = IdentityVerifierNotAvailableError(
        "not available"
    )

    response = client.get(
        "/v1/oauth-broker/authorize", params=AUTHORIZE_PARAMS, follow_redirects=False
    )

    assert response.status_code == 503


def test_callback_stores_the_token_and_resumes_the_run(
    client: TestClient,
    mock_vault: MagicMock,
    mock_provider: MagicMock,
    mock_http_client: MagicMock,
) -> None:
    state = sign_state("run_1", "wfnr_1", "jane@acme.com", "org_1")

    response = client.get(
        "/v1/oauth-broker/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == (
        "https://app.getport.io/org_1/organization/workflow-run?runId=run_1"
    )
    mock_provider.exchange_code.assert_awaited_once_with(
        "auth-code", "https://ocean.acme.com/v1/oauth-broker/callback"
    )
    mock_http_client.post.assert_awaited_once_with(
        "https://api.getport.io/v1/workflows/runs/run_1/resume?nodeRunId=wfnr_1",
        headers={"Authorization": "Bearer token", "x-port-reserved-usage": "true"},
    )
    # Vault is keyed by the provider's own identity — no target is sent by the caller at all.
    org_id, actor_id, target, record = mock_vault.write.await_args.args
    assert (org_id, actor_id, target) == ("org_1", "jane@acme.com", "github-ocean")
    assert record.access_token == "gho_token"


def test_callback_rejects_a_tampered_state(
    client: TestClient, mock_vault: MagicMock
) -> None:
    response = client.get(
        "/v1/oauth-broker/callback",
        params={"code": "auth-code", "state": "forged.state"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    mock_vault.write.assert_not_called()


def test_callback_re_checks_the_actor_before_writing(
    client: TestClient, mock_vault: MagicMock, mock_verifier: MagicMock
) -> None:
    mock_verifier.verify_run_actor.side_effect = IdentityVerificationError("revoked")
    state = sign_state("run_1", "wfnr_1", "jane@acme.com", "org_1")

    response = client.get(
        "/v1/oauth-broker/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 403
    mock_vault.write.assert_not_called()


def test_callback_reports_a_rejected_code(
    client: TestClient, mock_provider: MagicMock, mock_vault: MagicMock
) -> None:
    mock_provider.exchange_code.side_effect = OAuthError("bad_verification_code")
    state = sign_state("run_1", "wfnr_1", "jane@acme.com", "org_1")

    response = client.get(
        "/v1/oauth-broker/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 502
    mock_vault.write.assert_not_called()


def test_callback_reports_a_failed_vault_write(
    client: TestClient, mock_vault: MagicMock
) -> None:
    mock_vault.write.side_effect = VaultError("access denied")
    state = sign_state("run_1", "wfnr_1", "jane@acme.com", "org_1")

    response = client.get(
        "/v1/oauth-broker/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 502
