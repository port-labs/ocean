from integrations.sailpoint.exporters.identities import IdentitiesExporter


async def test_identities(run_exporter, patch_http_client):
    rows = await run_exporter(IdentitiesExporter)
    # 1st page (2 items) + 2nd page (1 item) = 3
    assert len(rows) == 3
    # verify shape
    assert rows[0]["id"] == "id_0"
    # called the identities endpoint at least twice due to pagination
    calls = [c for c in patch_http_client.calls if c["url"].endswith("/identities")]
    assert len(calls) >= 2
