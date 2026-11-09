from azure_integration.foundry.helpers.catalog_sync import normalize_catalog_payload
from azure_integration.foundry.kinds import ObjectKind


def test_normalize_catalog_payload_agent_flattens_definition() -> None:
    raw = {
        "id": "Omby-agent",
        "state": "enabled",
        "versions": {
            "latest": {
                "version": "1",
                "status": "active",
                "definition": {"kind": "prompt", "model": "gpt-5"},
            }
        },
    }
    normalized = normalize_catalog_payload(ObjectKind.AGENT, raw)
    assert normalized["model"] == "gpt-5"
    assert normalized["kind"] == "prompt"


def test_normalize_catalog_payload_conversation() -> None:
    normalized = normalize_catalog_payload(
        ObjectKind.CONVERSATION,
        {
            "id": "conv_1",
            "created_at": 1_700_000_000,
            "participant_agent_ids": ["Omby-agent"],
        },
    )
    assert normalized["id"] == "conv_1"
    assert normalized["participant_agent_ids"] == ["Omby-agent"]


def test_normalize_catalog_payload_deployment() -> None:
    normalized = normalize_catalog_payload(
        ObjectKind.MODEL_DEPLOYMENT,
        {"name": "gpt-5", "modelName": "gpt-5", "sku": {"name": "GlobalStandard"}},
    )
    assert normalized["id"] == "gpt-5"
    assert normalized["sku"] == "GlobalStandard"
