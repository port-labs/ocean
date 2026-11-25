import pytest

from tools.integration_validation.mock_server.admin_schemas import JournalEntry
from tools.integration_validation.runner.results import collect as collect_module
from tools.integration_validation.runner.results.collect import collect_scenario
from tools.integration_validation.runner.core.errors import ValidationFailedError
from tools.integration_validation.runner.results.mock_journal import MockJournal
from tools.integration_validation.runner.port.client import ScenarioPortPlan
from tools.integration_validation.runner.core.statuses import ResyncStatus
from tools.integration_validation.tests.runner.test_port_client import FakePortClient

MOCK_BASE_URL = "http://127.0.0.1:9000"


@pytest.fixture
def plan() -> ScenarioPortPlan:
    return ScenarioPortPlan(
        scenario_name="happy_path",
        integration_identifier="validate-sample-happy-path",
        blueprints=[{"identifier": "user-hp"}, {"identifier": "team-hp"}],
        blueprint_renames={"user": "user-hp", "team": "team-hp"},
        port_app_config={"resources": []},
        kinds=[],
    )


@pytest.fixture(autouse=True)
def journal(monkeypatch: pytest.MonkeyPatch) -> MockJournal:
    journal = MockJournal(
        requests=[
            JournalEntry(
                method="GET",
                path="/api/v2/users",
                query={},
                headers={},
                matched_route_id=None,
                response_status=599,
            )
        ],
        route_call_counts={"list-teams": 0},
    )

    async def fake_fetch(mock_base_url: str) -> MockJournal:
        assert mock_base_url == MOCK_BASE_URL
        return journal

    monkeypatch.setattr(collect_module, "fetch_mock_journal", fake_fetch)
    return journal


async def test_collects_resync_status_entities_by_blueprint_and_journal(
    plan: ScenarioPortPlan, journal: MockJournal
) -> None:
    team = {"identifier": "platform", "blueprint": "team-hp"}
    client = FakePortClient(
        entities={"team-hp": [team]}, resync_status=ResyncStatus.FAILED
    )

    collection = await collect_scenario(client, plan, mock_base_url=MOCK_BASE_URL)

    assert collection.resync_status == ResyncStatus.FAILED
    assert collection.entities == {"user": [], "team": [team]}
    assert collection.mock is journal
    assert collection.to_dict() == {
        "resync_status": "failed",
        "entity_counts": {"user": 0, "team": 1},
        "mock": {
            "request_count": 1,
            "unmatched_requests": [
                {"method": "GET", "path": "/api/v2/users", "query": {}}
            ],
            "unused_routes": ["list-teams"],
            "route_call_counts": {"list-teams": 0},
        },
    }


async def test_port_rejection_while_collecting_is_a_validation_failure(
    plan: ScenarioPortPlan,
) -> None:
    client = FakePortClient(fail_on=("search_entities", "team-hp"))

    with pytest.raises(ValidationFailedError, match="happy_path.*entities/search"):
        await collect_scenario(client, plan, mock_base_url=MOCK_BASE_URL)


def test_unknown_port_status_is_missing() -> None:
    assert ResyncStatus.from_port("completed") == ResyncStatus.COMPLETED
    assert ResyncStatus.from_port(None) == ResyncStatus.MISSING
    assert ResyncStatus.from_port("queued") == ResyncStatus.MISSING
