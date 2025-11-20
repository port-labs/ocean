from integrations.sailpoint.client import TOKEN_PATH, SailPointClient

from .conftest import FakeResponse, fixture_json


async def test_limit_offset_pagination(fake_http, cfg):
    base = f"https://{cfg.auth.tenant}.api.sailpoint.com"
    fake_http.register(
        "POST", f"{base}{TOKEN_PATH}", FakeResponse(200, fixture_json("token.json"))
    )

    fake_http.register(
        "GET",
        f"{base}/v2025/identities?limit=2&offset=0",
        FakeResponse(200, fixture_json("identities_page1.json")),
    )
    fake_http.register(
        "GET",
        f"{base}/v2025/identities?limit=2&offset=2",
        FakeResponse(200, fixture_json("identities_page2.json")),
    )

    c = SailPointClient(cfg)

    items = []
    async for it in c.paginate(
        "/v2025/identities", params={"limit": cfg.runtime.page_size, "offset": 0}
    ):
        items.append(it["id"])

    assert items == ["id-1", "id-2", "id-3"]
