from typing import Any

import httpx
import pytest

from port_ocean.core.models import Migration
from tools.integration_validation.runner.errors import (
    ValidationFailedError,
    ValidationSetupError,
)
from tools.integration_validation.runner.port_setup import (
    ScenarioPortPlan,
    prepare_scenario_port,
    teardown_scenario_port,
)

PORT_APP_CONFIG = {"resources": [{"kind": "team"}]}


def _http_error(method: str, path: str, status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request(method, f"https://api.port.io/v1{path}")
    response = httpx.Response(status_code, request=request, text='{"error":"bad"}')
    return httpx.HTTPStatusError("failed", request=request, response=response)


class FakePortClient:
    def __init__(
        self,
        fail_on: tuple[str, str] | None = None,
        status_code: int = 422,
        existing_blueprints: set[str] | None = None,
    ):
        self.calls: list[tuple[str, Any]] = []
        self.blueprints: set[str] = set(existing_blueprints or ())
        self._fail_on = fail_on
        self._status_code = status_code

    def _maybe_fail(self, operation: str, target: str, method: str, path: str) -> None:
        if self._fail_on == (operation, target):
            raise _http_error(method, path, self._status_code)

    async def create_blueprint(self, raw_blueprint: dict[str, Any]) -> dict[str, Any]:
        identifier = raw_blueprint["identifier"]
        self.calls.append(("create_blueprint", raw_blueprint))
        self._maybe_fail("create_blueprint", identifier, "POST", "/blueprints")
        self.blueprints.add(identifier)
        return raw_blueprint

    async def patch_blueprint(
        self, identifier: str, raw_blueprint: dict[str, Any]
    ) -> None:
        self.calls.append(("patch_blueprint", raw_blueprint))
        self._maybe_fail(
            "patch_blueprint", identifier, "PATCH", f"/blueprints/{identifier}"
        )

    async def delete_blueprint_with_entities(self, identifier: str) -> str | None:
        self.calls.append(("delete_blueprint", identifier))
        self._maybe_fail(
            "delete_blueprint", identifier, "DELETE", f"/blueprints/{identifier}"
        )
        if identifier not in self.blueprints:
            return None
        self.blueprints.remove(identifier)
        return f"migration-{identifier}"

    async def wait_for_migration_to_complete(
        self, migration_id: str, interval: int = 5
    ) -> Migration:
        self.calls.append(("wait_for_migration", migration_id))
        return Migration(
            id=migration_id,
            actor="test",
            sourceBlueprint="",
            mapping={},
            status="COMPLETED",
        )

    async def create_validation_integration(
        self, port_app_config: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append(("create_integration", port_app_config))
        self._maybe_fail("create_integration", "", "POST", "/integration")
        return {}

    async def mark_port_resources_initialized(self) -> None:
        self.calls.append(("mark_initialized", None))
        self._maybe_fail("mark_initialized", "", "PATCH", "/integration/x")

    async def delete_validation_integration(self) -> None:
        self.calls.append(("delete_integration", None))

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


PRE_RUN_CLEANUP = ["delete_integration", "delete_blueprint", "delete_blueprint"]


@pytest.fixture
def plan() -> ScenarioPortPlan:
    return ScenarioPortPlan(
        scenario_name="happy_path",
        integration_identifier="validate-sample-happy-path",
        blueprints=[
            {"identifier": "user-a1b2", "title": "User"},
            {
                "identifier": "team-a1b2",
                "title": "Team",
                "relations": {"members": {"target": "user-a1b2", "many": True}},
                "mirrorProperties": {"x": {"path": "members.$title"}},
            },
        ],
        blueprint_renames={"user": "user-a1b2", "team": "team-a1b2"},
        port_app_config=PORT_APP_CONFIG,
    )


async def test_prepare_creates_blueprints_in_stages_then_integration(
    plan: ScenarioPortPlan,
) -> None:
    client = FakePortClient()

    await prepare_scenario_port(client, plan)

    calls = client.calls[len(PRE_RUN_CLEANUP) :]
    assert client.names()[: len(PRE_RUN_CLEANUP)] == PRE_RUN_CLEANUP
    assert [name for name, _ in calls] == [
        "create_blueprint",
        "create_blueprint",
        "patch_blueprint",
        "patch_blueprint",
        "patch_blueprint",
        "patch_blueprint",
        "create_integration",
        "mark_initialized",
    ]
    created_team = calls[1][1]
    relation_patch = calls[3][1]
    full_patch = calls[5][1]
    assert "relations" not in created_team
    assert "relations" in relation_patch and "mirrorProperties" not in relation_patch
    assert "mirrorProperties" in full_patch
    assert calls[6][1] == PORT_APP_CONFIG


async def test_prepare_first_removes_resources_left_by_a_previous_run(
    plan: ScenarioPortPlan,
) -> None:
    client = FakePortClient(existing_blueprints={"user-a1b2"})

    await prepare_scenario_port(client, plan)

    assert client.names()[:4] == [*PRE_RUN_CLEANUP, "wait_for_migration"]
    assert client.blueprints == {"user-a1b2", "team-a1b2"}


async def test_prepare_fails_when_previous_run_resources_cannot_be_removed(
    plan: ScenarioPortPlan,
) -> None:
    client = FakePortClient(fail_on=("delete_blueprint", "user-a1b2"))

    with pytest.raises(ValidationSetupError, match="previous run: blueprint user-a1b2"):
        await prepare_scenario_port(client, plan)

    assert "create_blueprint" not in client.names()


async def test_prepare_rolls_back_blueprints_when_a_patch_is_rejected(
    plan: ScenarioPortPlan,
) -> None:
    client = FakePortClient(fail_on=("patch_blueprint", "team-a1b2"))

    with pytest.raises(ValidationFailedError, match="Port rejected PATCH"):
        await prepare_scenario_port(client, plan)

    assert "create_integration" not in client.names()
    assert client.blueprints == set()


async def test_prepare_rolls_back_created_blueprints_when_a_create_is_rejected(
    plan: ScenarioPortPlan,
) -> None:
    client = FakePortClient(fail_on=("create_blueprint", "team-a1b2"))

    with pytest.raises(ValidationFailedError):
        await prepare_scenario_port(client, plan)

    assert client.blueprints == set()


async def test_prepare_deletes_integration_when_marking_initialized_fails(
    plan: ScenarioPortPlan,
) -> None:
    client = FakePortClient(fail_on=("mark_initialized", ""))

    with pytest.raises(ValidationFailedError):
        await prepare_scenario_port(client, plan)

    assert client.names()[-5:] == [
        "delete_integration",
        "delete_blueprint",
        "wait_for_migration",
        "delete_blueprint",
        "wait_for_migration",
    ]
    assert client.blueprints == set()


async def test_prepare_reports_auth_failures_as_setup_errors(
    plan: ScenarioPortPlan,
) -> None:
    client = FakePortClient(fail_on=("create_blueprint", "user-a1b2"), status_code=401)

    with pytest.raises(ValidationSetupError, match="401"):
        await prepare_scenario_port(client, plan)


async def test_teardown_deletes_dependents_first_and_reports_leftovers(
    plan: ScenarioPortPlan,
) -> None:
    client = FakePortClient(
        fail_on=("delete_blueprint", "user-a1b2"),
        existing_blueprints={"user-a1b2", "team-a1b2"},
    )

    leftovers = await teardown_scenario_port(client, plan)

    assert leftovers == ["blueprint user-a1b2"]
    deleted = [target for name, target in client.calls if name == "delete_blueprint"]
    assert client.names()[0] == "delete_integration"
    assert deleted == ["team-a1b2", "user-a1b2"]
