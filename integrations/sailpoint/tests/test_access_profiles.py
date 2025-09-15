from integrations.sailpoint.exporters.access_profiles import \
    AccessProfilesExporter


async def test_access_profiles(run_exporter):
    rows = await run_exporter(AccessProfilesExporter)
    names = {r["name"] for r in rows}
    assert {"Corp IT Onboarding", "SRE Elevated"} <= names
