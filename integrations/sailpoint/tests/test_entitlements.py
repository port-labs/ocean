from integrations.sailpoint.exporters.entitlements import EntitlementsExporter


async def test_entitlements(run_exporter):
    rows = await run_exporter(EntitlementsExporter)
    assert any(r["name"] == "Admin" for r in rows)
