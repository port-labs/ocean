import integrations.sailpoint.mapping as mapping
from integrations.sailpoint.client import TOKEN_PATH, SailPointClient
from integrations.sailpoint.exporters.identities import IdentitiesExporter

from .conftest import FakeResponse, fixture_json


async def test_identities_exporter_streams_entities(
    fake_http, cfg, ocean_ctx, monkeypatch
):
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

    client = SailPointClient(cfg)
    ocean, ingested = ocean_ctx

    exp = IdentitiesExporter(client, mapping=mapping, cfg=cfg)
    await exp.ingest(ocean)

    # We streamed 3 entities total (two pages)
    assert len(ingested["streams"]) == 1
    streamed = ingested["streams"][0]
    assert len(streamed) == 3

    # Check shape for one entity
    ada = streamed[0]["entity"]
    assert ada["identifier"] == "id-1"
    assert ada["properties"]["email"] == "ada@example.com"
