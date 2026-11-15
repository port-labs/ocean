from collections.abc import AsyncIterator
from typing import Any

import pytest

from clients.devin_client import DevinClient
from core.sessions import DevinSessions


@pytest.fixture
def devin_sessions() -> DevinSessions:
    return DevinSessions(
        DevinClient(
            api_host="https://api.devin.ai/", api_key="cog_test", org_id="org-1"
        )
    )


async def test_list_by_tag_skips_unparseable_items(
    devin_sessions: DevinSessions,
) -> None:
    good: dict[str, Any] = {
        "session_id": "good-1",
        "url": "https://app.devin.ai/sessions/good-1",
        "status": "running",
        "tags": ["port:pending:inst"],
        "created_at": 1,
        "updated_at": 2,
    }
    bad = {"status": "running"}

    async def paginate(
        *_args: object, **_kwargs: object
    ) -> AsyncIterator[list[dict[str, Any]]]:
        yield [good, bad]

    devin_sessions.client.paginate = paginate  # type: ignore[method-assign]

    pages = [page async for page in devin_sessions.list_by_tag("port:pending:inst")]

    assert len(pages) == 1
    assert [session.session_id for session in pages[0]] == ["good-1"]
