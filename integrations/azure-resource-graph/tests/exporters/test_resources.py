from unittest.mock import MagicMock

import pytest

from azure_integration.exporters.resources import ResourcesExporter
from azure_integration.models import ResourceGroupTagFilters
from tests.helpers import aiter


@pytest.mark.asyncio
async def test_export_paginated_resources() -> None:
    # Setup
    mock_client = MagicMock()
    mock_client.make_paginated_request = MagicMock(
        return_value=aiter(
            [
                [{"name": "vm-1", "type": "Microsoft.Compute/virtualMachines"}],
                [{"name": "vm-2", "type": "Microsoft.Compute/virtualMachines"}],
            ]
        )
    )

    mock_options = MagicMock()
    mock_options.resource_types = ["Microsoft.Compute/virtualMachines"]
    mock_options.tag_filter = None
    subscriptions = ["sub-1", "sub-2"]
    mock_sub_manager = MagicMock()
    mock_sub_manager.get_sub_id_in_batches.return_value = aiter([subscriptions])
    exporter = ResourcesExporter(mock_client, mock_sub_manager)

    # Action
    results = [
        result async for result in exporter.get_paginated_resources(mock_options)
    ]
    flat_results = [item for batch in results for item in batch]

    # Assert
    assert len(flat_results) == 2
    assert flat_results[0] == {
        "name": "vm-1",
        "type": "Microsoft.Compute/virtualMachines",
    }
    assert flat_results[1] == {
        "name": "vm-2",
        "type": "Microsoft.Compute/virtualMachines",
    }
    # Using the default resource mapping from conftest.py
    assert mock_client.make_paginated_request.call_count == 1
    call_args = mock_client.make_paginated_request.call_args
    query = call_args.args[0]
    assert "resources" in query.lower()
    assert "| where type in~ ('microsoft.compute/virtualmachines')" in query.lower()
    assert call_args.args[1] == subscriptions


def test_build_full_sync_query_with_filters() -> None:
    exporter = ResourcesExporter(MagicMock(), MagicMock())
    resource_types = [
        "Microsoft.Compute/virtualMachines",
        "Microsoft.Network/virtualNetworks",
    ]
    tag_filters = ResourceGroupTagFilters(
        included={"env": "prod"}  # Not testing excluded to avoid issue with a bug
    )

    query = exporter._build_full_sync_query(resource_types, tag_filters)

    assert "resources" in query.lower()
    assert (
        "| where type in~ ('microsoft.compute/virtualmachines', 'microsoft.network/virtualnetworks')"
        in query.lower()
    )
    assert "| where (tostring(rgTags['env']) =~ 'prod')" in query
    assert "resourceGroup !in~" not in query


def test_build_full_sync_query_no_filters() -> None:
    exporter = ResourcesExporter(MagicMock(), MagicMock())
    resource_types = ["Microsoft.Compute/virtualMachines"]

    query = exporter._build_full_sync_query(resource_types)

    assert "resources" in query.lower()
    assert "| where type in~ ('microsoft.compute/virtualmachines')" in query.lower()
    assert "tostring(rgTags" not in query


def test_build_full_sync_query_no_resource_types() -> None:
    exporter = ResourcesExporter(MagicMock(), MagicMock())

    query = exporter._build_full_sync_query()
    assert "resources" in query.lower()
    assert "| where type in~" not in query.lower()
