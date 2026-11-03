from unittest.mock import AsyncMock, patch

import pytest
from port_ocean.clients.port.types import UserAgentType
from port_ocean.core.models import Entity

from gitlab_integration.events.hooks.push import _apply_gitops_diff


def _entity(identifier: str, title: str = "") -> Entity:
    return Entity(identifier=identifier, blueprint="service", title=title)


@pytest.mark.asyncio
async def test_apply_gitops_diff_writes_changes_directly_to_port() -> None:
    with patch("gitlab_integration.events.hooks.push.ocean") as mock_ocean:
        mock_ocean.register = AsyncMock()
        mock_ocean.unregister = AsyncMock()
        await _apply_gitops_diff(
            [_entity("kept"), _entity("removed")],
            [_entity("kept", "renamed"), _entity("added")],
        )

    mock_ocean.register.assert_awaited_once_with(
        [_entity("added"), _entity("kept", "renamed")], UserAgentType.gitops
    )
    mock_ocean.unregister.assert_awaited_once_with(
        [_entity("removed")], UserAgentType.gitops
    )
