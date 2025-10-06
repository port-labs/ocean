from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_integration.exporters.resource_containers import ResourceContainersExporter
from azure_integration.models import ResourceGroupTagFilters
from tests.helpers import aiter


@pytest.mark.asyncio
async def test_sync_for_subscriptions():
    # Setup
    mock_client = MagicMock()
    # Mock the async generator
    mock_client.run_query = MagicMock(
        return_value=aiter(
            [
                [
                    {
                        "name": "rg-1",
                        "type": "Microsoft.Resources/subscriptions/resourceGroups",
                        "tags": {"env": "prod"},
                    }
                ],
                [
                    {
                        "name": "rg-2",
                        "type": "Microsoft.Resources/subscriptions/resourceGroups",
                        "tags": {"env": "dev"},
                    }
                ],
            ]
        )
    )

    mock_resource_config = SimpleNamespace(selector=SimpleNamespace(tags=None))
    exporter = ResourceContainersExporter(mock_client, mock_resource_config)
    subscriptions = ["sub-1", "sub-2"]

    # Action
    results = [
        result async for result in exporter._sync_for_subscriptions(subscriptions)
    ]
    flat_results = [item for batch in results for item in batch]

    # Assert
    assert len(flat_results) == 2
    assert flat_results[0] == {
        "name": "rg-1",
        "type": "Microsoft.Resources/subscriptions/resourceGroups",
        "tags": {"env": "prod"},
    }
    assert flat_results[1] == {
        "name": "rg-2",
        "type": "Microsoft.Resources/subscriptions/resourceGroups",
        "tags": {"env": "dev"},
    }
    mock_client.run_query.assert_called_once()
    call_args = mock_client.run_query.call_args
    # First argument is the query string
    assert (
        "where type =~ 'microsoft.resources/subscriptions/resourcegroups'"
        in call_args.args[0].lower()
    )
    # Second argument is the subscriptions list
    assert call_args.args[1] == subscriptions


def test_build_sync_query_with_filters():
    exporter = ResourceContainersExporter(MagicMock(), MagicMock())
    tag_filters = ResourceGroupTagFilters(
        included={"env": "prod", "owner": "team-a"}, excluded={"legacy": "true"}
    )

    query = exporter._build_sync_query(tag_filters)

    assert "where type =~ 'microsoft.resources/subscriptions/resourcegroups'" in query.lower()
    assert (
        "| where (tostring(tags['env']) =~ 'prod' and tostring(tags['owner']) =~ 'team-a')"
        in query
    )
    assert "and not (tostring(tags['legacy']) =~ 'true')" in query


def test_build_sync_query_no_filters():
    exporter = ResourceContainersExporter(MagicMock(), MagicMock())
    query = exporter._build_sync_query()
    assert "where type =~ 'microsoft.resources/subscriptions/resourcegroups'" in query.lower()
    assert "tostring(tags" not in query.lower()
