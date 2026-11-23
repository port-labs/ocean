from __future__ import annotations

from azure_integration.foundry.core.exporters.endpoint_scoped_exporter import (
    EndpointScopedExporter,
)
from azure_integration.foundry.core.options import (
    ListResponsesOptions,
    SingleResponseOptions,
)
from azure_integration.foundry.foundry_incremental import RESPONSE_INCREMENTAL


class ResponsesExporter(
    EndpointScopedExporter[ListResponsesOptions, SingleResponseOptions]
):
    """Responses via agent protocol and/or project openai/v1 list APIs."""

    resource = "responses"
    strategy = RESPONSE_INCREMENTAL
