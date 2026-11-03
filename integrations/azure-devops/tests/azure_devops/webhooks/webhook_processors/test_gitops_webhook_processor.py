from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.models import Entity

from azure_devops.webhooks.webhook_processors.gitops_webhook_processor import (
    GitopsWebhookProcessor,
)

MODULE = "azure_devops.webhooks.webhook_processors.gitops_webhook_processor"


def _entity(identifier: str, title: str = "") -> dict[str, Any]:
    return {"identifier": identifier, "blueprint": "service", "title": title}


@pytest.mark.asyncio
async def test_ref_update_writes_the_commit_diff_to_port() -> None:
    processor = GitopsWebhookProcessor(
        WebhookEvent(trace_id="t", payload={}, headers={})
    )
    processor._resolved_client = MagicMock()
    config = MagicMock(spec_path="port.yml")
    push = {"resource": {"repository": {"id": "repo-1"}}}
    update = {"oldObjectId": "old", "newObjectId": "new"}
    entities_by_commit = {
        "new": [_entity("kept", "renamed"), _entity("added")],
        "old": [_entity("kept"), _entity("removed")],
    }

    async def generate(
        client: Any, spec_path: str, commit: str, repo_id: str
    ) -> list[dict[str, Any]]:
        return entities_by_commit[commit]

    with (
        patch(f"{MODULE}.generate_entities_from_commit_id", side_effect=generate),
        patch(f"{MODULE}.ocean") as mock_ocean,
    ):
        mock_ocean.register = AsyncMock()
        mock_ocean.unregister = AsyncMock()
        await processor._process_ref_update(config, push, update)

    registered, user_agent = mock_ocean.register.await_args.args
    assert {e.identifier for e in registered} == {"kept", "added"}
    assert user_agent == UserAgentType.gitops
    mock_ocean.unregister.assert_awaited_once_with(
        [Entity(**_entity("removed"))], UserAgentType.gitops
    )
