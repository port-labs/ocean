from integrations.sailpoint.client import TOKEN_PATH, SailPointClient

from .conftest import FakeResponse, fixture_json


async def test_client_credentials_token_refresh(fake_http, cfg):
    base = f"https://{cfg.auth.tenant}.api.sailpoint.com"

    fake_http.register(
        "POST", f"{base}{TOKEN_PATH}", FakeResponse(200, fixture_json("token.json"))
    )

    fake_http.register(
        "GET", f"{base}/v2025/identities", FakeResponse(200, {"data": []})
    )

    client = SailPointClient(cfg)
    result = await client.get("/v2025/identities")
    assert result == {"data": []}
    assert fake_http.calls[0]["url"].endswith(TOKEN_PATH)
