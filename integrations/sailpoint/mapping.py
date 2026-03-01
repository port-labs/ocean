from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


def _get(d: Dict[str, Any], path: str, default=None):
    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
        if cur is None:
            return default
    return cur


def _iso(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    try:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v
    except Exception:
        return v


def _ensure_list(v: Any) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


# ---------- IDENTITY ----------
def map_identity(sp: Dict[str, Any]) -> Dict[str, Any]:
    sid = sp["id"]
    title = sp.get("displayName") or sp.get("name") or sid
    account_ids = [
        a.get("id")
        for a in _ensure_list(sp.get("accounts"))
        if isinstance(a, dict) and a.get("id")
    ]
    entitlement_ids = [
        e.get("id")
        for e in _ensure_list(sp.get("entitlements"))
        if isinstance(e, dict) and e.get("id")
    ]
    role_ids = [
        r.get("id")
        for r in _ensure_list(sp.get("roles"))
        if isinstance(r, dict) and r.get("id")
    ]

    entity = {
        "identifier": sid,
        "title": title,
        "properties": {
            "email": sp.get("email"),
            "status": sp.get("status"),
            "createdAt": _iso(sp.get("created")),
            "updatedAt": _iso(sp.get("modified")),
            "identityProfileId": _get(sp, "identityProfile.id"),
        },
        "relations": {
            "accounts": [aid for aid in account_ids],
            "entitlements": [eid for eid in entitlement_ids],
            "roles": [rid for rid in role_ids],
        },
    }
    return entity


# ---------- ACCOUNT ----------
def map_account(sp: Dict[str, Any]) -> Dict[str, Any]:
    sid = sp["id"]
    title = sp.get("name") or sp.get("nativeIdentity") or sid
    identity_id = _get(sp, "identity.id") or sp.get("identityId")
    source_id = _get(sp, "source.id") or sp.get("sourceId")

    entitlement_ids = [
        e.get("id")
        for e in _ensure_list(sp.get("entitlements"))
        if isinstance(e, dict) and e.get("id")
    ]

    entity = {
        "identifier": sid,
        "title": title,
        "properties": {
            "name": sp.get("name"),
            "nativeIdentity": sp.get("nativeIdentity"),
            "status": sp.get("status"),
            "identityId": identity_id,
            "sourceId": source_id,
            "lastSyncedAt": _iso(sp.get("lastSynced")),
            "createdAt": _iso(sp.get("created")),
            "updatedAt": _iso(sp.get("modified")),
        },
        "relations": {
            "identity": identity_id,
            "source": source_id,
            "entitlements": [eid for eid in entitlement_ids],
        },
    }
    return entity


# ---------- ENTITLEMENT ----------
def map_entitlement(sp: Dict[str, Any]) -> Dict[str, Any]:
    sid = sp["id"]
    title = sp.get("name") or sid
    source_id = _get(sp, "source.id") or sp.get("sourceId")

    access_profile_ids = [
        ap.get("id")
        for ap in _ensure_list(sp.get("accessProfiles"))
        if isinstance(ap, dict) and ap.get("id")
    ]
    role_ids = [
        r.get("id")
        for r in _ensure_list(sp.get("roles"))
        if isinstance(r, dict) and r.get("id")
    ]
    identity_ids = [
        i.get("id")
        for i in _ensure_list(sp.get("identities"))
        if isinstance(i, dict) and i.get("id")
    ]
    account_ids = [
        a.get("id")
        for a in _ensure_list(sp.get("accounts"))
        if isinstance(a, dict) and a.get("id")
    ]

    entity = {
        "identifier": sid,
        "title": title,
        "properties": {
            "name": sp.get("name"),
            "description": sp.get("description"),
            "attribute": sp.get("attribute"),
            "value": sp.get("value"),
            "riskScore": sp.get("riskScore"),
            "sourceId": source_id,
            "createdAt": _iso(sp.get("created")),
            "updatedAt": _iso(sp.get("modified")),
        },
        "relations": {
            "source": source_id,
            "accessProfiles": access_profile_ids,
            "roles": role_ids,
            "identities": identity_ids,
            "accounts": account_ids,
        },
    }
    return entity


# ---------- ACCESS PROFILE ----------
def map_access_profile(sp: Dict[str, Any]) -> Dict[str, Any]:
    sid = sp["id"]
    title = sp.get("name") or sid
    owner_id = _get(sp, "owner.id") or sp.get("ownerId")

    entitlement_ids = [
        e.get("id")
        for e in _ensure_list(sp.get("entitlements"))
        if isinstance(e, dict) and e.get("id")
    ]
    role_ids = [
        r.get("id")
        for r in _ensure_list(sp.get("roles"))
        if isinstance(r, dict) and r.get("id")
    ]
    identity_ids = [
        i.get("id")
        for i in _ensure_list(sp.get("identities"))
        if isinstance(i, dict) and i.get("id")
    ]

    entity = {
        "identifier": sid,
        "title": title,
        "properties": {
            "name": sp.get("name"),
            "description": sp.get("description"),
            "type": sp.get("type"),
            "ownerId": owner_id,
            "createdAt": _iso(sp.get("created")),
            "updatedAt": _iso(sp.get("modified")),
        },
        "relations": {
            "entitlements": entitlement_ids,
            "roles": role_ids,
            "identities": identity_ids,
        },
    }
    return entity


# ---------- ROLE ----------
def map_role(sp: Dict[str, Any]) -> Dict[str, Any]:
    sid = sp["id"]
    title = sp.get("name") or sid
    owner_id = _get(sp, "owner.id") or sp.get("ownerId")

    access_profile_ids = [
        ap.get("id")
        for ap in _ensure_list(sp.get("accessProfiles"))
        if isinstance(ap, dict) and ap.get("id")
    ]
    entitlement_ids = [
        e.get("id")
        for e in _ensure_list(sp.get("entitlements"))
        if isinstance(e, dict) and e.get("id")
    ]
    identity_ids = [
        i.get("id")
        for i in _ensure_list(sp.get("identities"))
        if isinstance(i, dict) and i.get("id")
    ]

    entity = {
        "identifier": sid,
        "title": title,
        "properties": {
            "name": sp.get("name"),
            "description": sp.get("description"),
            "type": sp.get("type"),
            "riskScore": sp.get("riskScore"),
            "ownerId": owner_id,
            "createdAt": _iso(sp.get("created")),
            "updatedAt": _iso(sp.get("modified")),
        },
        "relations": {
            "accessProfiles": access_profile_ids,
            "entitlements": entitlement_ids,
            "identities": identity_ids,
        },
    }
    return entity


# ---------- SOURCE ----------
def map_source(sp: Dict[str, Any]) -> Dict[str, Any]:
    sid = sp["id"]
    title = sp.get("name") or sid

    account_ids = [
        a.get("id")
        for a in _ensure_list(sp.get("accounts"))
        if isinstance(a, dict) and a.get("id")
    ]
    entitlement_ids = [
        e.get("id")
        for e in _ensure_list(sp.get("entitlements"))
        if isinstance(e, dict) and e.get("id")
    ]

    entity = {
        "identifier": sid,
        "title": title,
        "properties": {
            "name": sp.get("name"),
            "description": sp.get("description"),
            "connectorType": sp.get("connectorType"),
            "authoritative": sp.get("authoritative"),
            "status": sp.get("status"),
            "createdAt": _iso(sp.get("created")),
            "updatedAt": _iso(sp.get("modified")),
        },
        "relations": {
            "accounts": account_ids,
            "entitlements": entitlement_ids,
        },
    }
    return entity


# ---------- Bonus: generic mapping hook ----------
def map_generic(
    sp: Dict[str, Any],
    id_field: str = "id",
    title_fields: Iterable[str] = ("name", "displayName"),
) -> Dict[str, Any]:
    sid = sp.get(id_field) or sp["id"]
    title = next((sp.get(f) for f in title_fields if sp.get(f)), sid)
    props = {k: v for k, v in sp.items() if k not in ("relations",)}
    return {"identifier": sid, "title": title, "properties": props, "relations": {}}
