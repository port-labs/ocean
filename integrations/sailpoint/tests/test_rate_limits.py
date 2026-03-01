from integrations.sailpoint.client import TOKEN_PATH, SailPointClient

from .conftest import FakeResponse, fixture_json


async def test_429_retry_after_respected(fake_http, cfg, monkeypatch):
    base = f"https://{cfg.auth.tenant}.api.sailpoint.com"
    fake_http.register(
        "POST", f"{base}{TOKEN_PATH}", FakeResponse(200, fixture_json("token.json"))
    )

    # First call returns 429 with Retry-After: 0.01, then success
    retry_headers = {"Retry-After": "0.01"}
    seq = [
        FakeResponse(429, {"error": "rate limit"}, headers=retry_headers),
        FakeResponse(200, {"data": []}),
    ]
    fake_http.register("GET", f"{base}/v2025/identities?limit=2&offset=0", seq)

    c = SailPointClient(cfg)
    res = await c.get("/v2025/identities", params={"limit": 2, "offset": 0})
    assert res == {"data": []}
