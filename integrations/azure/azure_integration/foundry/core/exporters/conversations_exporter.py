from __future__ import annotations

from azure_integration.foundry.core.exporters.endpoint_scoped_exporter import (
    EndpointScopedExporter,
)
from azure_integration.foundry.foundry_incremental import CONVERSATION_INCREMENTAL


class ConversationsExporter(EndpointScopedExporter):
    """Conversations via agent protocol and/or project openai/v1 list APIs."""

    resource = "conversations"
    strategy = CONVERSATION_INCREMENTAL
