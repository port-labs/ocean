from pydantic import BaseModel
import pytest
import os
from pytest_httpx import HTTPXMock
from typing import Any
from port_ocean.tests.helpers.ocean_app import (
    get_raw_result_on_integration_sync_resource_config,
)
import re


class TenureDuration(BaseModel):
    period_iso: str
    sort_factor: int
    humanize: str


class ReportsTo(BaseModel):
    display_name: str
    email: str
    surname: str
    first_name: str
    id: str


class CustomColumns(BaseModel):
    column_1689923448119: str
    column_1708713324447: str
    column_1659977358302: str


class Work(BaseModel):
    start_date: str
    manager: str
    work_phone: str
    tenure_duration: TenureDuration
    reports_to: ReportsTo
    indirect_reports: int
    site_id: int
    department: str
    tenure_years: int
    custom_columns: CustomColumns
    is_manager: bool
    title: str
    site: str
    direct_reports: int


class Profile(BaseModel):
    display_name: str
    work: Work
    company_id: int
    email: str
    surname: str
    id: str
    first_name: str


JOHN_DOE = Profile(
    display_name="John Doe",
    work=Work(
        start_date="2021-11-01",
        manager="1234567890123456789",
        work_phone="",
        tenure_duration=TenureDuration(
            period_iso="P3Y1M27D",
            sort_factor=1137,
            humanize="3 years, 1 month and 27 days",
        ),
        reports_to=ReportsTo(
            display_name="Jane Smith",
            email="j.smith@fakemail.com",
            surname="Smith",
            first_name="Jane",
            id="1234567890123456789",
        ),
        indirect_reports=3,
        site_id=2216118,
        department="Sales",
        tenure_years=3,
        custom_columns=CustomColumns(
            column_1689923448119="",
            column_1708713324447="456789012",
            column_1659977358302="",
        ),
        is_manager=True,
        title="Manager",
        site="Tel Aviv, Israel",
        direct_reports=3,
    ),
    company_id=123456,
    email="j.doe@fakemail.com",
    surname="Doe",
    id="7890123456789012345",
    first_name="John",
)

EMILY_CARTER = Profile(
    display_name="Emily Carter",
    work=Work(
        start_date="2022-02-22",
        manager="9876543210987654321",
        work_phone="",
        tenure_duration=TenureDuration(
            period_iso="P2Y10M6D",
            sort_factor=1026,
            humanize="2 years, 10 months and 6 days",
        ),
        reports_to=ReportsTo(
            display_name="Robert Brown",
            email="r.brown@fakemail.com",
            surname="Brown",
            first_name="Robert",
            id="9876543210987654321",
        ),
        indirect_reports=2,
        site_id=2216120,
        department="Marketing",
        tenure_years=3,
        custom_columns=CustomColumns(
            column_1689923448119="",
            column_1708713324447="567890123",
            column_1659977358302="",
        ),
        is_manager=False,
        title="Specialist",
        site="Kuala Lumpur, Malaysia",
        direct_reports=0,
    ),
    company_id=654321,
    email="e.carter@fakemail.com",
    surname="Carter",
    id="4567890123456789012",
    first_name="Emily",
)


class ListItem(BaseModel):
    id: str
    value: str
    name: str
    archived: bool
    children: list  # type: ignore


class ListStruct(BaseModel):
    name: str
    values: list[ListItem]
    items: list[ListItem]


# Lists
WORKING_LOCATIONS = ListStruct(
    name="workingLocations",
    values=[
        ListItem(
            id="onsite",
            value="Onsite/hybrid",
            name="Onsite/hybrid",
            archived=False,
            children=[],
        ),
        ListItem(
            id="remote",
            value="Remote",
            name="Remote",
            archived=False,
            children=[],
        ),
    ],
    items=[
        ListItem(
            id="onsite",
            value="Onsite/hybrid",
            name="Onsite/hybrid",
            archived=False,
            children=[],
        ),
        ListItem(
            id="remote",
            value="Remote",
            name="Remote",
            archived=False,
            children=[],
        ),
    ],
)

COMPLIANCE_CONSENT_STATUSES = ListStruct(
    name="complianceConsentStatuses",
    values=[
        ListItem(
            id="expired",
            value="Expired",
            name="Expired",
            archived=False,
            children=[],
        ),
        ListItem(
            id="pending_initial_consent",
            value="Pending initial consent",
            name="Pending initial consent",
            archived=False,
            children=[],
        ),
    ],
    items=[
        ListItem(
            id="expired",
            value="Expired",
            name="Expired",
            archived=False,
            children=[],
        ),
        ListItem(
            id="pending_initial_consent",
            value="Pending initial consent",
            name="Pending initial consent",
            archived=False,
            children=[],
        ),
    ],
)

TEAMS = ListStruct(
    name="teams",
    values=[
        ListItem(
            id="team1",
            value="Engineering",
            name="Engineering",
            archived=False,
            children=[],
        ),
        ListItem(
            id="team2",
            value="Marketing",
            name="Marketing",
            archived=False,
            children=[],
        ),
    ],
    items=[
        ListItem(
            id="team1",
            value="Engineering",
            name="Engineering",
            archived=False,
            children=[],
        ),
        ListItem(
            id="team2",
            value="Marketing",
            name="Marketing",
            archived=False,
            children=[],
        ),
    ],
)

PROFILES_RESPONSE_RAW = {"employees": [JOHN_DOE.dict(), EMILY_CARTER.dict()]}

LISTS_RESPONSE_RAW = {
    "workingLocations": WORKING_LOCATIONS.dict(),
    "complianceConsentStatuses": COMPLIANCE_CONSENT_STATUSES.dict(),
    "teams": TEAMS.dict(),
}

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


async def assert_on_results(results: Any, kind: str) -> None:
    assert len(results) > 0
    resync_results, errors = results
    entities = resync_results
    assert len(entities) > 0
    if kind == "profile":
        assert len(entities) == 2
        assert entities[0] == JOHN_DOE
        assert entities[1] == EMILY_CARTER
    elif kind == "list":
        assert len(entities) == 3
        assert entities[0] == WORKING_LOCATIONS
        assert entities[1] == COMPLIANCE_CONSENT_STATUSES
        assert entities[2] == TEAMS
    else:
        pytest.fail(f"unsupported object kind: {kind}")


async def test_full_sync_with_http_mock(
    get_mocked_ocean_app: Any,
    get_mock_ocean_resource_configs: Any,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url=re.compile(".*/v1/profiles"), json=PROFILES_RESPONSE_RAW
    )
    httpx_mock.add_response(
        url=re.compile(".*/v1/company/named-lists"), json=LISTS_RESPONSE_RAW
    )

    app = get_mocked_ocean_app()
    resource_configs = get_mock_ocean_resource_configs()

    for resource_config in resource_configs:
        results = await get_raw_result_on_integration_sync_resource_config(
            app, resource_config
        )
        await assert_on_results(results, resource_config.kind)
