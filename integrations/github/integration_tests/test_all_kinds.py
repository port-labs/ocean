import os
from typing import Any

import pytest

from port_ocean.integration_testing import IntegrationTestHarness, ResyncResult

from expectations import KIND_EXPECTATIONS, FieldPath, KindExpectation
from helpers import integration_config, mapping_for_kind
from mocks.transport_builder import GithubMockTransportBuilder

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

KIND_BUILDERS: dict[str, str] = {
    "user": "with_user_routes",
    "team": "with_team_routes",
    "pull-request-graphql": "with_pull_request_graphql_routes",
    "issue": "with_issue_routes",
    "release": "with_release_routes",
    "tag": "with_tag_routes",
    "environment": "with_environment_routes",
    "workflow": "with_workflow_routes",
    "workflow-run": "with_workflow_run_routes",
    "branch": "with_branch_routes",
    "branch-protection": "with_branch_protection_routes",
    "branch-detailed": "with_branch_detailed_routes",
    "dependabot-alert": "with_dependabot_alert_routes",
    "code-scanning-alerts": "with_code_scanning_alert_routes",
    "secret-scanning-alerts": "with_secret_scanning_alert_routes",
    "deployment": "with_deployment_routes",
    "deployment-status": "with_deployment_status_routes",
    "collaborator": "with_collaborator_routes",
    "package": "with_package_routes",
}

assert set(KIND_EXPECTATIONS) == set(
    KIND_BUILDERS
), "KIND_EXPECTATIONS and KIND_BUILDERS must cover the same kinds"


@pytest.mark.parametrize("kind", list(KIND_BUILDERS))
@pytest.mark.asyncio
async def test_kind_resyncs(kind: str) -> None:
    builder = GithubMockTransportBuilder().with_base()
    getattr(builder, KIND_BUILDERS[kind])()
    transport = builder.build(strict=True)

    mapping = mapping_for_kind(kind)
    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping,
        third_party_transport=transport,
        config_overrides=integration_config(),
    )

    try:
        await harness.start()
        result = await harness.trigger_resync()
    finally:
        await harness.shutdown()

    _assert_kind_resync(result, kind, mapping["resources"][0]["kind"])


def _assert_kind_resync(result: ResyncResult, kind: str, resource_kind: str) -> None:
    assert result.errors == [], f"Resync had errors for {kind}: {result.errors}"
    assert (
        result.reconciliation_success is True
    ), f"Reconciliation failed for {kind}: {result.errors}"

    items = result.raw_items(resource_kind)
    expectation = KIND_EXPECTATIONS[kind]

    _assert_item_count(items, expectation, kind)
    _assert_item_contents(items, expectation, kind)


def _lookup(item: dict[str, Any], path: FieldPath) -> Any:
    if isinstance(path, str):
        return item.get(path)
    value: Any = item
    for part in path:
        value = value[part]
    return value


def _assert_item_count(
    items: list[dict[str, Any]],
    expectation: KindExpectation,
    kind: str,
) -> None:
    assert (
        len(items) == expectation.count
    ), f"Expected {expectation.count} raw {kind} items, got {len(items)}: {items}"


def _assert_item_contents(
    items: list[dict[str, Any]],
    expectation: KindExpectation,
    kind: str,
) -> None:
    key_fields = tuple(expectation.records[0].key)
    assert all(
        tuple(expected.key) == key_fields for expected in expectation.records
    ), f"All {kind} records must be keyed by {key_fields}"

    items_by_key = {
        tuple(item.get(name) for name in key_fields): item for item in items
    }
    expected_keys = {tuple(expected.key.values()) for expected in expectation.records}
    assert len(items_by_key) == len(items), f"Duplicate {kind} keys: {items}"
    assert items_by_key.keys() == expected_keys, (
        f"Unexpected {kind} keys {key_fields}. "
        f"expected={sorted(expected_keys)} actual={sorted(items_by_key)}"
    )
    for expected in expectation.records:
        key = tuple(expected.key.values())
        item = items_by_key[key]
        for path, value in expected.fields.items():
            actual = _lookup(item, path)
            assert actual == value, (
                f"{kind}/{key} field {path!r} mismatch: "
                f"expected {value!r}, got {actual!r}"
            )
