import integrations.sailpoint.mapping as mapping
from integrations.sailpoint.client import TOKEN_PATH, SailPointClient
from integrations.sailpoint.exporters.access_profiles import \
    AccessProfilesExporter
from integrations.sailpoint.exporters.accounts import AccountsExporter
from integrations.sailpoint.exporters.entitlements import EntitlementsExporter
from integrations.sailpoint.exporters.roles import RolesExporter
from integrations.sailpoint.exporters.sources import SourcesExporter

from .conftest import FakeResponse, fixture_json


async def test_other_exporters(fake_http, cfg, ocean_ctx):
    base = f"https://{cfg.auth.tenant}.api.sailpoint.com"
    fake_http.register(
        "POST", f"{base}{TOKEN_PATH}", FakeResponse(200, fixture_json("token.json"))
    )
    fake_http.register(
        "GET",
        f"{base}/v2025/accounts?limit=2&offset=0",
        FakeResponse(200, fixture_json("accounts_page.json")),
    )
    fake_http.register(
        "GET",
        f"{base}/v2025/entitlements?limit=2&offset=0",
        FakeResponse(200, fixture_json("entitlements_page.json")),
    )
    fake_http.register(
        "GET",
        f"{base}/v2025/roles?limit=2&offset=0",
        FakeResponse(200, fixture_json("roles_page.json")),
    )
    fake_http.register(
        "GET",
        f"{base}/v2025/access-profiles?limit=2&offset=0",
        FakeResponse(200, fixture_json("access_profiles_page.json")),
    )
    fake_http.register(
        "GET",
        f"{base}/v2025/sources?limit=2&offset=0",
        FakeResponse(200, fixture_json("sources_page.json")),
    )

    client = SailPointClient(cfg)
    ocean, ingested = ocean_ctx

    for exporter_cls in (
        AccountsExporter,
        EntitlementsExporter,
        RolesExporter,
        AccessProfilesExporter,
        SourcesExporter,
    ):
        exp = exporter_cls(client, mapping=mapping, cfg=cfg)
        await exp.ingest(ocean)

    assert len(ingested["streams"]) == 5
    acct_stream = ingested["streams"][0]
    assert acct_stream[0]["entity"]["identifier"] == "acct-1"
