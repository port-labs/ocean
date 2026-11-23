from coralogix.clients.client import PaginationStyle
from coralogix.core.exporters.alert_definition_exporter import AlertDefinitionExporter
from tests.conftest import TEAM_URL, load_example, strip_team
from tests.coralogix.core.exporters.helpers import collect, mock_client

ALERT = strip_team(load_example("alert-definition"))


async def test_paginates_alert_defs_with_query_tokens() -> None:
    client = mock_client(pages=[[ALERT], [ALERT]])
    alerts = await collect(AlertDefinitionExporter(client).get_paginated_resources())
    assert len(alerts) == 2
    assert alerts[0]["__teamUrl"] == TEAM_URL
    (args, kwargs) = client.paginated_calls[0]
    assert args[0].endswith("alerts/alerts/v3")
    assert kwargs["data_key"] == "alertDefs"
    assert kwargs["style"] == PaginationStyle.TOKEN_QUERY


async def test_get_single_resource_unwraps_alert_def() -> None:
    client = mock_client({f"alerts/alerts/v3/{ALERT['id']}": {"alertDef": ALERT}})
    assert (
        await AlertDefinitionExporter(client).get_single_resource(ALERT["id"]) == ALERT
    )
