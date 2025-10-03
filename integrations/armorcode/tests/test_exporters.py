import pytest
from typing import Any, AsyncGenerator
from unittest.mock import MagicMock

from armorcode.clients.http.armorcode_client import ArmorcodeClient
from armorcode.core.exporters import (
    ProductExporter,
    SubProductExporter,
    FindingExporter,
)


async def _agen(
    batches: list[list[dict[str, Any]]]
) -> AsyncGenerator[list[dict[str, Any]], None]:
    for batch in batches:
        yield batch


@pytest.mark.asyncio
async def test_product_exporter_yields_batches() -> None:
    batches = [[{"id": "p1"}], [{"id": "p2"}]]
    client = MagicMock(spec=ArmorcodeClient)
    client.send_paginated_request.return_value = _agen(batches)

    exporter = ProductExporter(client)

    collected: list[dict[str, Any]] = []
    async for batch in exporter.get_paginated_resources():
        collected.extend(batch)

    assert [item["id"] for item in collected] == ["p1", "p2"]
    client.send_paginated_request.assert_called_once_with(
        endpoint="user/product/elastic/paged",
        method="GET",
    )
    assert exporter.get_resource_kind() == "product"


@pytest.mark.asyncio
async def test_subproduct_exporter_yields_batches() -> None:
    batches = [[{"id": "sp1"}], [{"id": "sp2"}]]
    client = MagicMock(spec=ArmorcodeClient)
    client.send_paginated_request.return_value = _agen(batches)

    exporter = SubProductExporter(client)

    collected: list[dict[str, Any]] = []
    async for batch in exporter.get_paginated_resources():
        collected.extend(batch)

    assert [item["id"] for item in collected] == ["sp1", "sp2"]
    client.send_paginated_request.assert_called_once_with(
        endpoint="user/sub-product/elastic",
        method="GET",
    )
    assert exporter.get_resource_kind() == "sub-product"


@pytest.mark.asyncio
async def test_finding_exporter_yields_batches() -> None:
    batches = [[{"id": "f1"}], [{"id": "f2"}]]
    client = MagicMock(spec=ArmorcodeClient)
    client.send_paginated_request.return_value = _agen(batches)

    exporter = FindingExporter(client)

    collected: list[dict[str, Any]] = []
    async for batch in exporter.get_paginated_resources():
        collected.extend(batch)

    assert [item["id"] for item in collected] == ["f1", "f2"]
    client.send_paginated_request.assert_called_once_with(
        endpoint="api/findings",
        method="POST",
        json_data={},
        use_offset_pagination=False,
    )
    assert exporter.get_resource_kind() == "finding"
