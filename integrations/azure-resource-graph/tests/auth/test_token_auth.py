from datetime import datetime, timedelta, timezone

from azure_integration.auth.token_auth import AzureAccessToken, TokenCredential


def test_access_token_is_expired_logic() -> None:
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    t_future = AzureAccessToken(token="t", expires_at=future)
    t_past = AzureAccessToken(token="t", expires_at=past)

    assert t_future.is_expired is False
    assert t_past.is_expired is True


async def test_token_credential_returns_token() -> None:
    cred = TokenCredential()
    tok = await cred.get_token("scope")
    assert isinstance(tok, AzureAccessToken)
    assert isinstance(tok.token, str) and tok.token
