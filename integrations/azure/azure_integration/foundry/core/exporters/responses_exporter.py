from __future__ import annotations

from typing import Any

from azure_integration.foundry.core.exporters.endpoint_scoped_exporter import (
    EndpointScopedExporter,
)
from azure_integration.foundry.core.options import (
    ListResponsesOptions,
    SingleResponseOptions,
)
from azure_integration.foundry.foundry_incremental import RESPONSE_INCREMENTAL
from azure_integration.foundry.models.responses import Response


class ResponsesExporter(
    EndpointScopedExporter[ListResponsesOptions, SingleResponseOptions]
):
    """Responses via agent protocol and/or project openai/v1 list APIs."""

    resource = "responses"
    strategy = RESPONSE_INCREMENTAL

    async def in_progress(self, options: ListResponsesOptions) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        async for page in self.get_paginated_resources(options):
            rows.extend(
                item for item in page if Response.model_validate(item).is_in_progress()
            )
        return rows
