"""Load optional extension packs from integrations/fake-integration/extensions."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from port_ocean.context.ocean import ocean

from .types import FakeDepartment, FakePerson

EXTENSIONS_ROOT = Path(__file__).resolve().parent.parent / "extensions"
PACKS_ROOT = EXTENSIONS_ROOT / "packs"

# Optional JSON arrays under packs/<name>/. Missing file → caller falls back to
# loadgen / static defaults (packs are not person-only).
RESOURCE_FILES: Dict[str, str] = {
    "persons": "persons.json",
    "departments": "departments.json",
    "offices": "offices.json",
    "teams": "teams.json",
    "projects": "projects.json",
}


class FixturePackConfigKeys:
    FIXTURE_PACK = "fixture_pack"


def get_fixture_pack_name() -> Optional[str]:
    raw = ocean.integration_config.get(FixturePackConfigKeys.FIXTURE_PACK)
    if raw is None:
        raw = ocean.integration_config.get("fixturePack")
    if raw is None:
        return None
    name = str(raw).strip()
    return name or None


def pack_dir(pack_name: str) -> Path:
    return PACKS_ROOT / pack_name


def discover_pack_names() -> List[str]:
    """Auto-discover pack directories under extensions/packs/ (any optional resource JSON)."""
    if not PACKS_ROOT.is_dir():
        return []
    names: List[str] = []
    for path in sorted(PACKS_ROOT.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        has_resource = any(
            (path / filename).is_file() for filename in RESOURCE_FILES.values()
        )
        if has_resource or (path / "README.md").is_file():
            names.append(path.name)
    return names


def _load_json_array(path: Path, pack_name: str) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.name} in pack {pack_name!r} must be a JSON array")
    return data


@lru_cache(maxsize=32)
def load_pack_resource(pack_name: str, resource: str) -> Optional[List[Dict[str, Any]]]:
    """Return pack JSON for a resource kind, or None if that file is absent."""
    filename = RESOURCE_FILES.get(resource)
    if filename is None:
        filename = f"{resource}.json"
    path = pack_dir(pack_name) / filename
    if not path.is_file():
        return None
    return _load_json_array(path, pack_name)


@lru_cache(maxsize=8)
def load_pack_persons(pack_name: str) -> List[Dict[str, Any]]:
    rows = load_pack_resource(pack_name, "persons")
    if rows is None:
        raise FileNotFoundError(
            f"fixture pack persons.json missing: {pack_dir(pack_name) / 'persons.json'}"
        )
    return rows


def persons_for_department(
    pack_name: str, department_id: str, limit: int = -1
) -> List[Dict[str, Any]]:
    rows = [
        p
        for p in load_pack_persons(pack_name)
        if (p.get("department") or {}).get("id") == department_id
    ]
    if limit is not None and limit > 0:
        rows = rows[:limit]
    # Normalize through the model so shape matches generator output.
    out: List[Dict[str, Any]] = []
    for p in rows:
        dept = p.get("department") or {}
        person = FakePerson(
            id=p["id"],
            name=p["name"],
            email=p["email"],
            status=p["status"],
            age=p["age"],
            bio=p.get("bio") or "",
            department=FakeDepartment(
                id=dept["id"], name=dept.get("name") or dept["id"]
            ),
        )
        out.append(person.dict())
    return out


def clear_pack_cache() -> None:
    load_pack_persons.cache_clear()
    load_pack_resource.cache_clear()
