from typing import Any

from incident_io.core.exporters.schedule_exporter import (
    SCHEDULE_PAGE_SIZE,
    ScheduleExporter,
)
from incident_io.core.exporters.team_exporter import TeamExporter
from incident_io.core.exporters.user_exporter import UserExporter
from incident_io.core.options import UserOptions
from tests.incident_io.core.exporters.helpers import collect, mock_client

USER: dict[str, Any] = {"id": "user-1", "name": "Lisa", "email": "lisa@example.com"}
TEAM: dict[str, Any] = {"id": "team-1", "name": "Platform", "members": [USER]}
SCHEDULE: dict[str, Any] = {
    "id": "schedule-1",
    "name": "Primary On-call",
    "current_shifts": [{"user": USER}],
}


async def test_users_omit_inactive_by_default() -> None:
    client = mock_client(pages=[[USER]])
    assert await collect(
        UserExporter(client).get_paginated_resources(
            UserOptions(include_inactive=False)
        )
    ) == [USER]
    assert client.paginated_calls[0][1]["params"] == {}


async def test_users_include_inactive_when_asked() -> None:
    client = mock_client(pages=[[USER]])
    await collect(
        UserExporter(client).get_paginated_resources(UserOptions(include_inactive=True))
    )
    assert client.paginated_calls[0][1]["params"] == {"include_inactive": True}


async def test_get_single_user() -> None:
    client = mock_client({f"v2/users/{USER['id']}": {"user": USER}})
    assert await UserExporter(client).get_single_resource(USER["id"]) == USER


async def test_teams_list_and_unwrap() -> None:
    client = mock_client(
        responses={f"v3/teams/{TEAM['id']}": {"team": TEAM}},
        pages=[[TEAM]],
    )
    assert await collect(TeamExporter(client).get_paginated_resources()) == [TEAM]
    assert client.paginated_calls[0][0][0] == "v3/teams"
    assert await TeamExporter(client).get_single_resource(TEAM["id"]) == TEAM


async def test_schedules_request_the_shift_page_size() -> None:
    client = mock_client(
        responses={f"v2/schedules/{SCHEDULE['id']}": {"schedule": SCHEDULE}},
        pages=[[SCHEDULE]],
    )
    assert await collect(ScheduleExporter(client).get_paginated_resources()) == [
        SCHEDULE
    ]
    assert client.paginated_calls[0][1]["page_size"] == SCHEDULE_PAGE_SIZE
    assert (
        await ScheduleExporter(client).get_single_resource(SCHEDULE["id"]) == SCHEDULE
    )
