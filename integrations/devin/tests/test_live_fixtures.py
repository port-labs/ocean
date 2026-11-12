"""Locks shapes captured from the live Devin org during the P0 spike.

Session creation was rejected with `billing_restricted` / `out_of_quota`, so
these fixtures cover the calls that succeeded: empty session pages, a playbook
timestamp, the member lookup, and the create error body.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from actions.exceptions import DevinApiError
from clients.devin_client import DevinClient
from core.sessions import DevinSessions
from core.tracking.tags import pending_tag
from core.tracking.turn_state import to_epoch_seconds
from tests.fakes import INSTALLATION_ID, FakeDevin, FakePort, patched_ocean
from tests.test_client import _response
from tests.test_session_tracker import Clock, make_tracker, track_turn

FIXTURES = Path(__file__).parent / "fixtures"
SESSION_ID = "devin-live"


def _load(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return loaded


@pytest.fixture
def request_mock() -> AsyncMock:
    return AsyncMock(return_value=_response(200, {}))


@pytest.fixture
def client(request_mock: AsyncMock) -> DevinClient:
    instance = DevinClient(
        api_host="https://api.devin.ai/", api_key="cog_test", org_id="org-1"
    )
    instance._client = MagicMock()
    instance._client.request = request_mock
    return instance


@pytest.fixture
def devin() -> FakeDevin:
    return FakeDevin()


@pytest.fixture
def port() -> FakePort:
    return FakePort()


@pytest.fixture
def clock() -> Clock:
    return Clock(0)


@pytest.fixture
def ocean_mock(port: FakePort) -> Iterator[MagicMock]:
    with patched_ocean(port) as mock_ocean:
        yield mock_ocean


def test_live_playbook_timestamps_are_epoch_seconds() -> None:
    item = _load("playbooks_page.json")["body"]["items"][0]
    created_at = item["created_at"]
    updated_at = item["updated_at"]

    assert created_at == updated_at == 1_792_504_698
    assert to_epoch_seconds(created_at) == created_at


async def test_live_empty_session_page_stops_pagination(
    client: DevinClient, request_mock: AsyncMock
) -> None:
    request_mock.return_value = _response(200, _load("sessions_list.json")["body"])

    pages = [
        page
        async for page in client.paginate(
            "/sessions", params={"tags": [pending_tag(INSTALLATION_ID)]}
        )
    ]

    assert pages == [[]]
    assert request_mock.await_count == 1


async def test_live_member_payload_exposes_user_id(client: DevinClient) -> None:
    payload = _load("member_lookup_by_email.json")["body"]
    client.fetch_page = AsyncMock(return_value=payload)  # type: ignore[method-assign]

    user_id = await DevinSessions(client).find_user_id_by_email("user@example.com")

    assert user_id == payload["items"][0]["user_id"]
    assert user_id


def test_live_billing_error_detail_is_surfaced() -> None:
    body = _load("session_create_with_tags.json")["body"]
    request = httpx.Request(
        "POST", "https://api.devin.ai/v3/organizations/org/sessions"
    )
    response = httpx.Response(403, request=request, json=body)
    error = httpx.HTTPStatusError("forbidden", request=request, response=response)

    message = str(
        DevinApiError.from_http_error(error, "Failed to create the Devin session")
    )

    assert body["error_code"] == "billing_restricted"
    assert "out_of_quota" in message


@pytest.mark.usefixtures("ocean_mock")
async def test_live_second_timestamps_complete_an_exit_turn(
    devin: FakeDevin, port: FakePort, clock: Clock
) -> None:
    """A seconds-epoch `updated_at` from the live API must not be divided by 1000.

    Treating 1792504698 as milliseconds would make the turn look older than
    `sent_at` and the tracker would never complete it.
    """
    sent_at = _load("playbooks_page.json")["body"]["items"][0]["created_at"]
    clock.now = sent_at + 30
    track_turn(devin, port, session_id=SESSION_ID, sent_at=sent_at)
    devin.set_status(SESSION_ID, "exit", None, sent_at + 1)

    await make_tracker(devin, clock).tick()

    [completion] = port.completions["wfnr_1"]
    assert completion.success is True
    assert completion.output["durationSeconds"] == 1
    assert completion.status_label == "Session ended"
