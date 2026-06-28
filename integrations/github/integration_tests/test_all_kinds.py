import os

import pytest

from port_ocean.integration_testing import IntegrationTestHarness, ResyncResult

from expectations import KIND_EXPECTATIONS, KindExpectation
from helpers import integration_config, mapping_for_kind
from mocks.transport_builder import GithubMockTransportBuilder

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

KIND_BLUEPRINTS: dict[str, str] = {
    "user": "githubUser",
    "team": "githubTeam",
    "pull-request-graphql": "githubPullRequest",
    "issue": "githubIssue",
    "release": "githubRelease",
    "tag": "githubTag",
    "environment": "githubEnvironment",
    "workflow": "githubWorkflow",
    "workflow-run": "githubWorkflowRun",
    "branch": "githubBranch",
    "branch-protection": "githubBranch",
    "branch-detailed": "githubBranch",
    "dependabot-alert": "githubDependabotAlert",
    "code-scanning-alerts": "githubCodeScanningAlert",
    "secret-scanning-alerts": "githubSecretScanningAlert",
    "deployment": "githubDeployment",
    "deployment-status": "githubDeploymentStatus",
    "collaborator": "githubCollaborator",
}

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
}

assert set(KIND_EXPECTATIONS) == set(
    KIND_BLUEPRINTS
), "KIND_EXPECTATIONS and KIND_BLUEPRINTS must cover the same kinds"


@pytest.mark.parametrize("kind", list(KIND_BLUEPRINTS))
@pytest.mark.asyncio
async def test_kind_resyncs(kind: str) -> None:
    builder = GithubMockTransportBuilder().with_base()
    getattr(builder, KIND_BUILDERS[kind])()
    transport = builder.build(strict=True)

    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping_for_kind(kind),
        third_party_transport=transport,
        config_overrides=integration_config(),
    )

    try:
        await harness.start()
        result = await harness.trigger_resync()
    finally:
        await harness.shutdown()

    _assert_kind_resync(result, kind)


def _assert_kind_resync(result: ResyncResult, kind: str) -> None:
    assert result.errors == [], f"Resync had errors for {kind}: {result.errors}"
    assert (
        result.reconciliation_success is True
    ), f"Reconciliation failed for {kind}: {result.errors}"

    blueprint = KIND_BLUEPRINTS[kind]
    entities = [e for e in result.upserted_entities if e["blueprint"] == blueprint]
    expectation = KIND_EXPECTATIONS[kind]

    _assert_entity_count(entities, expectation, kind, blueprint)
    _assert_entity_contents(entities, expectation, kind)


def _assert_entity_count(
    entities: list[dict],
    expectation: KindExpectation,
    kind: str,
    blueprint: str,
) -> None:
    assert len(entities) == expectation.count, (
        f"Expected {expectation.count} {blueprint} entities for kind {kind}, "
        f"got {len(entities)}: {[e['identifier'] for e in entities]}"
    )


def _assert_entity_contents(
    entities: list[dict],
    expectation: KindExpectation,
    kind: str,
) -> None:
    entities_by_id = {entity["identifier"]: entity for entity in entities}
    expected_ids = {expected.identifier for expected in expectation.entities}
    assert entities_by_id.keys() == expected_ids, (
        f"Unexpected identifiers for kind {kind}. "
        f"expected={sorted(expected_ids)} actual={sorted(entities_by_id)}"
    )
    # logger.error(f"Entities: {entities_by_id}")
    for expected in expectation.entities:
        entity = entities_by_id[expected.identifier]
        if expected.title is not None:
            assert entity["title"] == expected.title, (
                f"{kind}/{expected.identifier} title mismatch: "
                f"expected {expected.title!r}, got {entity['title']!r}"
            )
        for key, value in expected.properties.items():
            assert entity["properties"].get(key) == value, (
                f"{kind}/{expected.identifier} property {key!r} mismatch: "
                f"expected {value!r}, got {entity['properties'].get(key)!r}"
            )
        for key, value in expected.relations.items():
            assert entity.get("relations", {}).get(key) == value, (
                f"{kind}/{expected.identifier} relation {key!r} mismatch: "
                f"expected {value!r}, got {entity.get('relations', {}).get(key)!r}"
            )
