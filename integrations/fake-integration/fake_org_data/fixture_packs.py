"""Load optional extension packs from integrations/fake-integration/extensions/."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from port_ocean.context.ocean import ocean

from .types import FakeDepartment, FakePerson

EXTENSIONS_ROOT = Path(__file__).resolve().parent.parent / "extensions"
PACKS_ROOT = EXTENSIONS_ROOT / "packs"


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


@lru_cache(maxsize=8)
def load_pack_persons(pack_name: str) -> List[Dict[str, Any]]:
    path = pack_dir(pack_name) / "persons.json"
    if not path.is_file():
        raise FileNotFoundError(f"fixture pack persons.json missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"persons.json in pack {pack_name!r} must be a JSON array")
    return data


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
            department=FakeDepartment(id=dept["id"], name=dept.get("name") or dept["id"]),
        )
        out.append(person.dict())
    return out


def clear_pack_cache() -> None:
    load_pack_persons.cache_clear()
