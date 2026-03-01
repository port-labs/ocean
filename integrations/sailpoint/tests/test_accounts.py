from integrations.sailpoint.exporters.accounts import AccountsExporter


async def test_accounts(run_exporter, patch_http_client):
    rows = await run_exporter(AccountsExporter)
    assert len(rows) == 3
    assert rows[0]["sourceId"] in {"src_okta", "src_azuread", "src_aws"}
