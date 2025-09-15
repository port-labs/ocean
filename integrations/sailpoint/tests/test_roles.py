from integrations.sailpoint.exporters.roles import RolesExporter


async def test_roles(run_exporter):
    rows = await run_exporter(RolesExporter)
    assert any(r["id"] == "role_2" for r in rows)
