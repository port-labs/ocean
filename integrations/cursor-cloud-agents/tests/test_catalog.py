from core.catalog import (
    enrich_v0_agent_raw_for_catalog,
    normalize_agent_raw_for_catalog,
)


def test_enrich_v0_agent_raw_maps_source_and_target_to_v1_fields() -> None:
    raw = {
        "id": "bc-1",
        "name": "Ok response handling",
        "status": "CREATING",
        "source": {"repository": "https://github.com/org/repo", "ref": "main"},
        "target": {"url": "https://cursor.com/agents?id=bc-1"},
        "createdAt": "2026-07-16T11:11:03.025Z",
    }

    enriched = enrich_v0_agent_raw_for_catalog(raw, console_host="https://cursor.com")

    assert enriched["repos"] == [{"url": "https://github.com/org/repo"}]
    assert enriched["url"] == "https://cursor.com/agents?id=bc-1"


def test_enrich_v0_agent_raw_builds_url_from_console_host() -> None:
    raw = {
        "id": "bc-1",
        "source": {"repository": "https://github.com/org/repo"},
    }

    enriched = enrich_v0_agent_raw_for_catalog(raw, console_host="https://cursor.com/")

    assert enriched["url"] == "https://cursor.com/agents/bc-1"


def test_normalize_agent_raw_maps_v0_creating_to_active() -> None:
    raw = {
        "id": "bc-1",
        "name": "Ok response handling",
        "status": "CREATING",
        "source": {"repository": "https://github.com/org/repo"},
        "target": {"url": "https://cursor.com/agents?id=bc-1"},
        "createdAt": "2026-07-16T11:11:03.025Z",
        "updatedAt": None,
    }

    normalized = normalize_agent_raw_for_catalog(raw, console_host="https://cursor.com")

    assert normalized == {
        "id": "bc-1",
        "name": "Ok response handling",
        "status": "ACTIVE",
        "source": {"repository": "https://github.com/org/repo"},
        "target": {"url": "https://cursor.com/agents?id=bc-1"},
        "repos": [{"url": "https://github.com/org/repo"}],
        "url": "https://cursor.com/agents?id=bc-1",
        "createdAt": "2026-07-16T11:11:03.025Z",
    }


def test_normalize_agent_raw_preserves_v1_statuses() -> None:
    assert (
        normalize_agent_raw_for_catalog({"id": "bc-1", "status": "ARCHIVED"})["status"]
        == "ARCHIVED"
    )
    assert (
        normalize_agent_raw_for_catalog({"id": "bc-1", "status": "ACTIVE"})["status"]
        == "ACTIVE"
    )
