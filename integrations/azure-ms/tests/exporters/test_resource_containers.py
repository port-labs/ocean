from unittest.mock import MagicMock

import pytest

from azure_integration.exporters.resource_containers import ResourceContainersExporter
from azure_integration.models import ResourceGroupTagFilters
from tests.helpers import aiter


@pytest.mark.asyncio
async def test_export_paginated_resources() -> None:
    # Setup
    mock_client = MagicMock()
    # Mock the async generator
    mock_client.make_paginated_request = MagicMock(
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

    mock_options = MagicMock()
    mock_options.tag_filter = None
    subscriptions = ["sub-1", "sub-2"]
    mock_sub_manager = MagicMock()
    mock_sub_manager.get_sub_id_in_batches.return_value = aiter([subscriptions])
    exporter = ResourceContainersExporter(mock_client, mock_sub_manager)

    # Action
    results = [result async for result in exporter.get_paginated_resources(mock_options)]
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
    mock_client.make_paginated_request.assert_called_once()
    call_args = mock_client.make_paginated_request.call_args
    # Second argument is the subscriptions list
    assert call_args.args[1] == subscriptions


def test_build_sync_query_with_filters() -> None:
    exporter = ResourceContainersExporter(MagicMock(), MagicMock())
    tag_filters = ResourceGroupTagFilters(
        included={"env": "prod", "owner": "team-a"}, excluded={"legacy": "true"}
    )

    query = exporter._build_sync_query(tag_filters)

    assert (
        "| where (tostring(tags['env']) =~ 'prod' and tostring(tags['owner']) =~ 'team-a')"
        in query
    )
    assert "and not (tostring(tags['legacy']) =~ 'true')" in query


def test_build_sync_query_no_filters() -> None:
    exporter = ResourceContainersExporter(MagicMock(), MagicMock())
    query = exporter._build_sync_query()
    assert "tostring(tags" not in query.lower()
