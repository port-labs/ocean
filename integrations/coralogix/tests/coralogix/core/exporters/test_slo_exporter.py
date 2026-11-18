from coralogix.core.exporters.slo_exporter import STATUS_KEY, SloExporter
from coralogix.core.options import SloOptions
from tests.conftest import TEAM_URL, load_example, strip_team
from tests.coralogix.core.exporters.helpers import collect, mock_client

SLO = {k: v for k, v in strip_team(load_example("slo")).items() if k != STATUS_KEY}
STATUS = load_example("slo")[STATUS_KEY]


async def test_attaches_status_and_team() -> None:
    client = mock_client(
        {"slo/slos/v1": {"slos": [SLO]}, f"slo/slos/v1/{SLO['id']}/status": STATUS}
    )
    slos = await collect(
        SloExporter(client).get_paginated_resources(SloOptions(include_status=True))
    )
    assert len(slos) == 1
    assert slos[0][STATUS_KEY] == STATUS
    assert slos[0]["__teamUrl"] == TEAM_URL


async def test_skips_status_calls_when_disabled() -> None:
    client = mock_client({"slo/slos/v1": {"slos": [SLO]}})
    slos = await collect(
        SloExporter(client).get_paginated_resources(SloOptions(include_status=False))
    )
    assert STATUS_KEY not in slos[0]
    endpoints = [c.args[0] for c in client.send_api_request.call_args_list]
    assert not any(e.endswith("/status") for e in endpoints)


async def test_missing_status_is_none() -> None:
    client = mock_client({"slo/slos/v1": {"slos": [SLO]}})
    slos = await collect(
        SloExporter(client).get_paginated_resources(SloOptions(include_status=True))
    )
    assert slos[0][STATUS_KEY] is None


async def test_no_slos_yields_nothing() -> None:
    client = mock_client({"slo/slos/v1": {}})
    assert (
        await collect(
            SloExporter(client).get_paginated_resources(SloOptions(include_status=True))
        )
        == []
    )


async def test_get_single_resource_unwraps_slo() -> None:
    client = mock_client({f"slo/slos/v1/{SLO['id']}": {"slo": SLO}})
    assert await SloExporter(client).get_single_resource(SLO["id"]) == SLO
