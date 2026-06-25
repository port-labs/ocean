import os

import pytest

from port_ocean.integration_testing import IntegrationTestHarness, ResyncResult

from helpers import integration_config, mapping_for_kind
from mocks.transport_builder import GithubMockTransportBuilder

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

KIND_BLUEPRINTS: dict[str, str] = {
    "issue": "githubIssue",
    "release": "githubRelease",
    "tag": "githubTag",
    "environment": "githubEnvironment",
    "workflow": "githubWorkflow",
    "branch": "githubBranch",
    "dependabot-alert": "githubDependabotAlert",
    "code-scanning-alerts": "githubCodeScanningAlert",
    "secret-scanning-alerts": "githubSecretScanningAlert",
    "deployment": "githubDeployment",
    "collaborator": "githubCollaborator",
}

KIND_BUILDERS: dict[str, str] = {
    "issue": "with_issue_routes",
    "release": "with_release_routes",
    "tag": "with_tag_routes",
    "environment": "with_environment_routes",
    "workflow": "with_workflow_routes",
    "branch": "with_branch_routes",
    "dependabot-alert": "with_dependabot_alert_routes",
    "code-scanning-alerts": "with_code_scanning_alert_routes",
    "secret-scanning-alerts": "with_secret_scanning_alert_routes",
    "deployment": "with_deployment_routes",
    "collaborator": "with_collaborator_routes",
}


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

    blueprint = KIND_BLUEPRINTS[kind]
    entities = [e for e in result.upserted_entities if e["blueprint"] == blueprint]
    assert entities, f"Expected {blueprint} entities for kind {kind}, got none"
