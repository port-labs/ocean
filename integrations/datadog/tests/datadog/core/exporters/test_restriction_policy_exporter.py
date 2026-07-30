from unittest.mock import AsyncMock, patch

import pytest

from datadog.client import DatadogClient
from datadog.core.exporters import RestrictionPolicyExporter


@pytest.mark.asyncio
async def test_enrich_resource_with_restriction_policy_extracts_principal_ids(
    mock_datadog_client: DatadogClient,
) -> None:
    exporter = RestrictionPolicyExporter(mock_datadog_client)
    resource = {"id": "7f772d6ea0545a6bac605ff6d9a47a04"}
    policy = {
        "type": "restriction_policy",
        "id": "slo:7f772d6ea0545a6bac605ff6d9a47a04",
        "attributes": {
            "bindings": [
                {
                    "relation": "editor",
                    "principals": [
                        "role:83659eba-5ce6-11f1-b7ce-da7ad0900002",
                        "team:aebefe35-c980-4b75-ad5b-86e246513f3b",
                        "user:1d9870ef-3c6d-11ef-b7f6-0ebe70fd121d",
                    ],
                },
                {
                    "relation": "viewer",
                    "principals": [
                        "org:dbb758e9-396e-11ef-800c-bea43249b5f6",
                        "user:1d9870ef-3c6d-11ef-b7f6-0ebe70fd121d",
                    ],
                },
            ]
        },
    }

    with patch.object(
        exporter, "get_resource", new_callable=AsyncMock, return_value=policy
    ):
        enriched = await exporter.enrich_resource_with_restriction_policy(
            "slo", resource
        )

    assert enriched["__restrictionPolicy"] == policy
    assert enriched["__restrictedUsers"] == ["1d9870ef-3c6d-11ef-b7f6-0ebe70fd121d"]
    assert enriched["__restrictedTeams"] == ["aebefe35-c980-4b75-ad5b-86e246513f3b"]
    assert enriched["__restrictedRoles"] == ["83659eba-5ce6-11f1-b7ce-da7ad0900002"]


@pytest.mark.asyncio
async def test_enrich_resource_with_restriction_policy_defaults_to_empty_principals(
    mock_datadog_client: DatadogClient,
) -> None:
    exporter = RestrictionPolicyExporter(mock_datadog_client)
    resource = {"id": "abc123"}

    with patch.object(
        exporter, "get_resource", new_callable=AsyncMock, return_value=None
    ):
        enriched = await exporter.enrich_resource_with_restriction_policy(
            "monitor", resource
        )

    assert enriched["__restrictionPolicy"] is None
    assert enriched["__restrictedUsers"] == []
    assert enriched["__restrictedTeams"] == []
    assert enriched["__restrictedRoles"] == []


def test_extract_restricted_principals_ignores_invalid_and_unknown_principals(
    mock_datadog_client: DatadogClient,
) -> None:
    exporter = RestrictionPolicyExporter(mock_datadog_client)
    policy = {
        "attributes": {
            "bindings": [
                {"principals": ["user:aaa", "team:bbb", "role:ccc", "org:ddd", "bad"]},
                {"principals": ["role:ccc", "user:eee", "team:bbb"]},
            ]
        }
    }

    users, teams, roles = exporter._extract_restricted_principals(policy)

    assert users == ["aaa", "eee"]
    assert teams == ["bbb"]
    assert roles == ["ccc"]
