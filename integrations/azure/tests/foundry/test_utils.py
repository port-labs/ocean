from datetime import UTC, datetime

from azure_integration.foundry.helpers.utils import (
    enrich_with_project,
    parse_foundry_timestamp,
    timestamp_to_iso,
)


def test_parse_foundry_timestamp_unix_string() -> None:
    parsed = parse_foundry_timestamp("1793724875")
    assert parsed == datetime.fromtimestamp(1793724875, tz=UTC)


def test_timestamp_to_iso_unix_string() -> None:
    assert timestamp_to_iso("1793724875") == (
        datetime.fromtimestamp(1793724875, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def test_parse_foundry_timestamp_iso_z() -> None:
    parsed = parse_foundry_timestamp("2026-01-15T12:00:00Z")
    assert parsed == datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def test_enrich_with_project_adds_identity_fields() -> None:
    enriched = enrich_with_project(
        {
            "id": "agent-1",
            "name": "demo",
            "created_at": 1731170000,
            "versions": {"latest": {"created_at": 1731170000}},
        },
        project_endpoint="https://acct.services.ai.azure.com/api/projects/demo/",
        project_id=(
            "/subscriptions/sub/resourceGroups/rg/providers/"
            "Microsoft.CognitiveServices/accounts/acct/projects/demo"
        ),
    )
    assert enriched["id"] == "agent-1"
    assert enriched["name"] == "demo"
    assert (
        enriched["__foundryProjectEndpoint"]
        == "https://acct.services.ai.azure.com/api/projects/demo"
    )
    assert enriched["__foundryProjectId"] == (
        "/subscriptions/sub/resourceGroups/rg/providers/"
        "Microsoft.CognitiveServices/accounts/acct/projects/demo"
    )
    assert enriched["__foundryProjectName"] == "demo"
    assert enriched["created_at"] == "2024-11-09T16:33:20Z"
    assert enriched["versions"]["latest"]["created_at"] == "2024-11-09T16:33:20Z"
