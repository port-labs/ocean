from typing import Any
from unittest.mock import MagicMock

import pytest

from fake_org_data import fixture_packs
from fake_org_data.fixture_packs import (
    clear_pack_cache,
    get_fixture_pack_name,
    load_pack_persons,
    persons_for_department,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    clear_pack_cache()
    yield
    clear_pack_cache()


def test_load_stable_org_persons() -> None:
    rows = load_pack_persons("stable-org")
    assert len(rows) == 10
    ids = {r["id"] for r in rows}
    assert "person-hr-001" in ids
    assert "person-morpazia-002" in ids


def test_persons_for_department_stable_ids() -> None:
    hr = persons_for_department("stable-org", "hr")
    assert [p["id"] for p in hr] == ["person-hr-001", "person-hr-002"]
    assert all(p["department"]["id"] == "hr" for p in hr)


def test_persons_for_department_limit() -> None:
    hr = persons_for_department("stable-org", "hr", limit=1)
    assert len(hr) == 1
    assert hr[0]["id"] == "person-hr-001"


def test_get_fixture_pack_name_from_snake_and_camel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"fixture_pack": "stable-org"}
    monkeypatch.setattr(fixture_packs, "ocean", mock_ocean)
    assert get_fixture_pack_name() == "stable-org"

    mock_ocean.integration_config = {"fixturePack": "stable-org"}
    assert get_fixture_pack_name() == "stable-org"

    mock_ocean.integration_config = {"fixture_pack": "  "}
    assert get_fixture_pack_name() is None

    mock_ocean.integration_config = {}
    assert get_fixture_pack_name() is None
