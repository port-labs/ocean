from pathlib import Path

import httpx
import pytest

from tools.integration_validation.mock_server.app import create_mock_server_app
from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.mock_journal import fetch_mock_journal
from tools.integration_validation.tests.mock_server.test_server import _write_routes

MOCK_BASE_URL = "http://mock.test"


async def test_fetch_mock_journal_reads_requests_unmatched_and_unused(
    tmp_path: Path,
) -> None:
    transport = httpx.ASGITransport(app=create_mock_server_app(_write_routes(tmp_path)))
    async with httpx.AsyncClient(base_url=MOCK_BASE_URL, transport=transport) as mock:
        await mock.post("/__admin/scenario", json={"routes": ["routes/team.yaml"]})
        await mock.get("/api/v2/team", params={"page": "0"})
        await mock.get("/api/v2/users")

    journal = await fetch_mock_journal(MOCK_BASE_URL, transport=transport)

    assert [entry.path for entry in journal.requests] == [
        "/api/v2/team",
        "/api/v2/users",
    ]
    assert journal.route_call_counts["list-teams"] == 1
    assert [entry.path for entry in journal.unmatched_requests] == ["/api/v2/users"]
    assert journal.unused_route_ids == ["create-team", "unused-route", "rate-limited"]
    assert journal.report_dict()["unmatched_requests"] == [
        {"method": "GET", "path": "/api/v2/users", "query": {}}
    ]


async def test_fetch_mock_journal_explains_an_unreachable_mock() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(ValidationSetupError, match="Is the mock server running"):
        await fetch_mock_journal(MOCK_BASE_URL, transport=httpx.MockTransport(refuse))


async def test_fetch_mock_journal_rejects_an_unexpected_payload() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"nope": 1}))

    with pytest.raises(ValidationSetupError, match="unexpected journal"):
        await fetch_mock_journal(MOCK_BASE_URL, transport=transport)
