from integrations.sailpoint.exporters.sources import SourcesExporter


async def test_sources(run_exporter):
    rows = await run_exporter(SourcesExporter)
    ids = {r["id"] for r in rows}
    assert {"src_okta", "src_azuread"} <= ids
