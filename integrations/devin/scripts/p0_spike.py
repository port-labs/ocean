"""P0 Devin API checks from HANDOVER.md §5.

Run from integrations/devin:
  poetry run python scripts/p0_spike.py

Writes redacted fixtures under tests/fixtures/. Prints a summary only.
Does not print the API key, org id, emails, or user ids.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

_ORG_RE = re.compile(r"org-[A-Za-z0-9]+")
_COG_RE = re.compile(r"cog_[A-Za-z0-9._\-]+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_USER_RE = re.compile(r"\buser-[A-Za-z0-9]+\b")


def _cfg() -> tuple[str, str, str, str]:
    load_dotenv(ROOT / ".env")
    host = os.environ.get(
        "OCEAN__INTEGRATION__CONFIG__DEVIN_API_HOST", "https://api.devin.ai"
    ).rstrip("/")
    key = os.environ["OCEAN__INTEGRATION__CONFIG__DEVIN_API_KEY"]
    org = os.environ["OCEAN__INTEGRATION__CONFIG__DEVIN_ORG_ID"]
    ident = os.environ.get("OCEAN__INTEGRATION__IDENTIFIER", "devin-local")
    return host, key, org, ident


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key == "name" and isinstance(item, str):
                redacted[key] = "Redacted"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(x) for x in value]
    if isinstance(value, str):
        value = _COG_RE.sub("cog_REDACTED", value)
        value = _ORG_RE.sub("org-REDACTED", value)
        value = _EMAIL_RE.sub("user@example.com", value)
        value = _USER_RE.sub("user-REDACTED", value)
    return value


def _save(name: str, payload: Any) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    path = FIXTURES / name
    path.write_text(json.dumps(_redact(payload), indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}")


def _epoch_unit(value: Any) -> str:
    if not isinstance(value, int):
        return f"not-int:{type(value).__name__}"
    if value > 10**12:
        return f"ms ({value})"
    if value > 10**9:
        return f"seconds ({value})"
    return f"small ({value})"


async def _request(
    client: Any,
    method: str,
    url: str,
    headers: dict[str, str],
    *,
    json_body: dict[str, Any] | None = None,
    params: list[tuple[str, str]] | None = None,
) -> tuple[int, Any]:
    response = await client.request(
        method,
        url,
        headers=headers,
        json=json_body,
        params=params,
        timeout=45.0,
    )
    try:
        body: Any = response.json()
    except json.JSONDecodeError:
        body = {"raw": response.text[:500]}
    return response.status_code, body


def _detail(body: Any) -> str:
    if isinstance(body, dict):
        return str(body.get("detail") or body.get("title") or "")[:180]
    return str(body)[:180]


async def main() -> int:
    import httpx

    host, key, org, ident = _cfg()
    base = f"{host}/v3/organizations/{org}"
    headers = {
        "Authorization": f"Bearer {key}",
        "content-type": "application/json",
    }
    results: dict[str, str] = {}
    notes: dict[str, Any] = {}
    created_ids: list[str] = []
    member_user_id: str | None = None

    async with httpx.AsyncClient() as client:
        print("catalog reads")
        status, sessions = await _request(
            client, "GET", f"{base}/sessions", headers, params=[("first", "2")]
        )
        _save("sessions_list.json", {"status": status, "body": _trim_list(sessions)})
        notes["sessions_list"] = _list_note(status, sessions)
        results["list_sessions"] = (
            f"HTTP {status} {_detail(sessions) if status >= 400 else ''}".strip()
        )

        for name, path in (
            ("playbooks", "/playbooks"),
            ("knowledge_notes", "/knowledge/notes"),
            ("secrets", "/secrets"),
        ):
            code, payload = await _request(
                client, "GET", f"{base}{path}", headers, params=[("first", "1")]
            )
            _save(f"{name}_page.json", {"status": code, "body": _trim_list(payload)})
            notes[name] = _list_note(code, payload)

        print("S7 member lookup")
        members_url = f"{host}/v3beta1/organizations/{org}/members/users"
        code, members = await _request(
            client, "GET", members_url, headers, params=[("first", "1")]
        )
        _save("member_lookup.json", {"status": code, "body": members})
        email = _first_email(members)
        if email and code < 400:
            code_f, filtered = await _request(
                client,
                "GET",
                members_url,
                headers,
                params=[("email", email), ("first", "1")],
            )
            _save(
                "member_lookup_by_email.json",
                {"status": code_f, "body": filtered},
            )
            item = _first_item(filtered)
            if isinstance(item, dict) and item.get("user_id"):
                member_user_id = str(item["user_id"])
            has_user_id = member_user_id is not None
            results["S7"] = (
                "confirmed"
                if code_f < 400 and has_user_id
                else f"differs HTTP {code_f} user_id={has_user_id}"
            )
            notes["S7"] = {
                "list_status": code,
                "filter_status": code_f,
                "field": "user_id" if has_user_id else "missing",
                "item_keys": sorted(item.keys()) if isinstance(item, dict) else [],
            }
        else:
            results["S7"] = f"HTTP {code}: {_detail(members)}"

        print("S1 create with port tags")
        long_external = "port:external-id:devin:" + ("wfnr_" + "a" * 31)
        pending = f"port:pending:{ident}"
        unique = f"spike-and-{int(time.time())}"
        tags = [
            "port:managed",
            pending,
            long_external,
            "port:sent-at:1760000000",
            unique,
        ]
        notes["tag_lengths"] = {tag: len(tag) for tag in tags}
        code, created = await _request(
            client,
            "POST",
            f"{base}/sessions",
            headers,
            json_body={"prompt": "Say hi and stop. Do not use tools.", "tags": tags},
        )
        _save("session_create_with_tags.json", {"status": code, "body": created})
        session_id = _session_id(created) if code < 400 else None
        if session_id:
            created_ids.append(session_id)
        if code >= 400:
            results["S1"] = f"blocked HTTP {code}: {_detail(created)}"
        else:
            returned = created.get("tags") or []
            missing = [tag for tag in tags if tag not in returned]
            results["S1"] = (
                "confirmed" if not missing else f"differs missing {len(missing)} tags"
            )
            notes["S1"] = {
                "status": created.get("status"),
                "status_detail": created.get("status_detail"),
                "created_at": _epoch_unit(created.get("created_at")),
                "updated_at": _epoch_unit(created.get("updated_at")),
                "tag_count": len(returned),
                "missing": missing,
                "session_id_prefix": session_id[:6] if session_id else None,
            }

        print("S2 list by tag")
        code, listed = await _request(
            client,
            "GET",
            f"{base}/sessions",
            headers,
            params=[("tags", pending), ("first", "10")],
        )
        _save("sessions_by_tag.json", {"status": code, "body": _trim_list(listed)})
        if code >= 400:
            results["S2"] = f"HTTP {code}: {_detail(listed)}"
        elif session_id:
            ids = _item_ids(listed)
            one_hit = session_id in ids
            code_and, listed_and = await _request(
                client,
                "GET",
                f"{base}/sessions",
                headers,
                params=[("tags", pending), ("tags", unique), ("first", "10")],
            )
            _save(
                "sessions_by_two_tags.json",
                {"status": code_and, "body": _trim_list(listed_and)},
            )
            code_miss, listed_miss = await _request(
                client,
                "GET",
                f"{base}/sessions",
                headers,
                params=[
                    ("tags", pending),
                    ("tags", "spike-and-does-not-exist"),
                    ("first", "10"),
                ],
            )
            and_hit = session_id in _item_ids(listed_and)
            miss_hit = session_id in _item_ids(listed_miss)
            if one_hit and and_hit and not miss_hit:
                semantics = "AND"
            elif one_hit and miss_hit:
                semantics = "filter ignored or OR"
            else:
                semantics = f"unexpected one={one_hit} and={and_hit} miss={miss_hit}"
            results["S2"] = (
                f"confirmed semantics={semantics}"
                if semantics == "AND"
                else f"differs {semantics}"
            )
            notes["S2"] = {
                "one_status": code,
                "and_status": code_and,
                "miss_status": code_miss,
                "semantics": semantics,
                "totals": {
                    "one": listed.get("total") if isinstance(listed, dict) else None,
                    "and": (
                        listed_and.get("total")
                        if isinstance(listed_and, dict)
                        else None
                    ),
                    "miss": (
                        listed_miss.get("total")
                        if isinstance(listed_miss, dict)
                        else None
                    ),
                },
            }
        else:
            results["S2"] = (
                f"request HTTP {code}; AND semantics not tested (no session)"
            )

        if not session_id:
            _save("spike_notes.json", {"results": results, "notes": notes})
            _print_summary(results, notes)
            return 1

        try:
            await _session_checks(
                client,
                headers,
                base,
                session_id,
                created,
                member_user_id,
                created_ids,
                results,
                notes,
            )
        finally:
            await _cleanup(client, headers, base, created_ids, results)

        if results.get("S1", "").startswith("confirmed"):
            print("S4b max_acu_limit=1")
            code, limited = await _request(
                client,
                "POST",
                f"{base}/sessions",
                headers,
                json_body={
                    "prompt": "Inspect the repository and summarize every top-level directory.",
                    "max_acu_limit": 1,
                    "tags": ["port:managed", "spike-acu-limit"],
                },
            )
            limited_id = _session_id(limited) if code < 400 else None
            if limited_id:
                created_ids.append(limited_id)
                trail = await _poll_status(
                    client, headers, base, limited_id, seconds=90, interval=10
                )
                notes["S4_acu"] = trail
                results["S4_acu"] = _trail_summary(trail)
                await _cleanup(client, headers, base, [limited_id], results)
            else:
                results["S4_acu"] = f"blocked HTTP {code}: {_detail(limited)}"

        _save("spike_notes.json", {"results": results, "notes": notes})

    _print_summary(results, notes)
    return 0


async def _session_checks(
    client: Any,
    headers: dict[str, str],
    base: str,
    session_id: str,
    created: dict[str, Any],
    member_user_id: str | None,
    created_ids: list[str],
    results: dict[str, str],
    notes: dict[str, Any],
) -> None:
    print("S6 messages")
    code, page = await _request(
        client,
        "GET",
        f"{base}/sessions/{session_id}/messages",
        headers,
        params=[("first", "2")],
    )
    _save("messages_page.json", {"status": code, "body": page})
    cursor = page.get("end_cursor") if isinstance(page, dict) else None
    has_next = page.get("has_next_page") if isinstance(page, dict) else None
    items = page.get("items") if isinstance(page, dict) else None
    sample = items[0] if isinstance(items, list) and items else {}
    notes["S6"] = {
        "status": code,
        "has_next_page": has_next,
        "end_cursor_type": type(cursor).__name__,
        "end_cursor_null": cursor is None,
        "item_keys": sorted(sample.keys()) if isinstance(sample, dict) else [],
        "source": sample.get("source") if isinstance(sample, dict) else None,
        "created_at": (
            _epoch_unit(sample.get("created_at")) if isinstance(sample, dict) else None
        ),
        "event_id_present": isinstance(sample, dict) and "event_id" in sample,
    }
    if cursor:
        code2, page2 = await _request(
            client,
            "GET",
            f"{base}/sessions/{session_id}/messages",
            headers,
            params=[("first", "2"), ("after", str(cursor))],
        )
        _save("messages_page_after.json", {"status": code2, "body": page2})
        notes["S6"]["after_status"] = code2
        notes["S6"]["after_has_next"] = (
            page2.get("has_next_page") if isinstance(page2, dict) else None
        )
        notes["S6"]["after_end_cursor_null"] = (
            page2.get("end_cursor") is None if isinstance(page2, dict) else None
        )
    results["S6"] = "confirmed" if code < 400 else f"HTTP {code}"

    print("S4 poll until a terminal-looking state or 120s")
    trail = await _poll_status(
        client, headers, base, session_id, seconds=120, interval=10
    )
    notes["S4_initial"] = trail
    results["S4_initial"] = _trail_summary(trail)
    _save(
        "session.json", {"status": 200, "body": trail[-1]["body"] if trail else created}
    )

    print("S3/S5 follow-up message")
    before = await _get_session(client, headers, base, session_id)
    before_updated = before.get("updated_at") if isinstance(before, dict) else None
    code, sent = await _request(
        client,
        "POST",
        f"{base}/sessions/{session_id}/messages",
        headers,
        json_body={"message": "Thanks, stop now."},
    )
    _save("message_send.json", {"status": code, "body": sent})
    fast: list[dict[str, Any]] = []
    if code < 400:
        for _ in range(8):
            await asyncio.sleep(1)
            snap = await _get_session(client, headers, base, session_id)
            fast.append(
                {
                    "status": snap.get("status"),
                    "status_detail": snap.get("status_detail"),
                    "updated_at": snap.get("updated_at"),
                    "updated_changed": snap.get("updated_at") != before_updated,
                }
            )
        notes["S5"] = fast
        stuck = [row["status_detail"] for row in fast[:3]]
        results["S5"] = f"observed first details={stuck}"
        after = fast[-1] if fast else {}
        results["S3"] = (
            f"created_at {_epoch_unit(before.get('created_at') if isinstance(before, dict) else None)}; "
            f"updated_at before {_epoch_unit(before_updated)} after {_epoch_unit(after.get('updated_at'))}; "
            f"updated_changed={after.get('updated_changed')}"
        )
    else:
        results["S3"] = f"send blocked HTTP {code}: {_detail(sent)}"
        results["S5"] = results["S3"]

    print("S9 tags")
    code_post, appended = await _request(
        client,
        "POST",
        f"{base}/sessions/{session_id}/tags",
        headers,
        json_body={"tags": ["spike-appended"]},
    )
    code_put, replaced = await _request(
        client,
        "PUT",
        f"{base}/sessions/{session_id}/tags",
        headers,
        json_body={"tags": ["port:managed"]},
    )
    _save(
        "session_tags.json",
        {
            "post": {"status": code_post, "body": appended},
            "put": {"status": code_put, "body": replaced},
        },
    )
    post_tags = appended.get("tags") if isinstance(appended, dict) else None
    put_tags = replaced.get("tags") if isinstance(replaced, dict) else None
    notes["S9"] = {
        "post_status": code_post,
        "put_status": code_put,
        "post_has_appended": isinstance(post_tags, list)
        and "spike-appended" in post_tags,
        "put_tags": put_tags,
    }
    if (
        code_post < 400
        and code_put < 400
        and notes["S9"]["post_has_appended"]
        and put_tags == ["port:managed"]
    ):
        results["S9"] = "confirmed POST appends, PUT replaces"
    else:
        results["S9"] = f"differs post={code_post} put={code_put}"

    await _impersonation_check(
        client, headers, base, member_user_id, created_ids, results, notes
    )


async def _impersonation_check(
    client: Any,
    headers: dict[str, str],
    base: str,
    user_id: str | None,
    created_ids: list[str],
    results: dict[str, str],
    notes: dict[str, Any],
) -> None:
    """S8 needs a key without ImpersonateOrgSessions. This key is the only one
    available, so record what create_as_user_id does when the permission is present.
    """
    if not user_id:
        results["S8"] = "blocked: member lookup did not return a user_id"
        return
    print("S8 create_as_user_id with the current key")
    code, created = await _request(
        client,
        "POST",
        f"{base}/sessions",
        headers,
        json_body={
            "prompt": "Reply with the single word ok.",
            "create_as_user_id": user_id,
            "tags": ["spike-impersonation"],
        },
    )
    _save("session_create_as_user.json", {"status": code, "body": created})
    session_id = _session_id(created) if code < 400 else None
    if session_id:
        created_ids.append(session_id)
    results["S8"] = f"HTTP {code} with permission present" + (
        f": {_detail(created)}" if code >= 400 else " (created)"
    )
    notes["S8"] = {"status": code, "created": session_id is not None}


async def _cleanup(
    client: Any,
    headers: dict[str, str],
    base: str,
    session_ids: list[str],
    results: dict[str, str],
) -> None:
    for session_id in session_ids:
        print("S10 terminate and archive")
        code_del, deleted = await _request(
            client,
            "DELETE",
            f"{base}/sessions/{session_id}",
            headers,
            params=[("archive", "true")],
        )
        code_arch, archived = await _request(
            client,
            "POST",
            f"{base}/sessions/{session_id}/archive",
            headers,
        )
        _save(
            "session_terminate_archive.json",
            {
                "delete": {"status": code_del, "body": deleted},
                "archive": {"status": code_arch, "body": archived},
            },
        )
        del_obj = isinstance(deleted, dict) and "session_id" in deleted
        arch_obj = isinstance(archived, dict) and "session_id" in archived
        results["S10"] = (
            f"DELETE {code_del} session_object={del_obj}; "
            f"POST archive {code_arch} session_object={arch_obj}"
        )
        if isinstance(deleted, dict):
            results["S4_terminate"] = (
                f"after DELETE status={deleted.get('status')} "
                f"detail={deleted.get('status_detail')}"
            )


async def _get_session(
    client: Any, headers: dict[str, str], base: str, session_id: str
) -> dict[str, Any]:
    _code, body = await _request(
        client, "GET", f"{base}/sessions/{session_id}", headers
    )
    return body if isinstance(body, dict) else {"raw": body}


async def _poll_status(
    client: Any,
    headers: dict[str, str],
    base: str,
    session_id: str,
    *,
    seconds: int,
    interval: int,
) -> list[dict[str, Any]]:
    trail: list[dict[str, Any]] = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        body = await _get_session(client, headers, base, session_id)
        row = {
            "status": body.get("status"),
            "status_detail": body.get("status_detail"),
            "updated_at": _epoch_unit(body.get("updated_at")),
            "acus_consumed": body.get("acus_consumed"),
            "body": body,
        }
        trail.append(row)
        pair = (row["status"], row["status_detail"])
        if pair[0] in {"exit", "error", "suspended"} or pair[1] in {
            "waiting_for_user",
            "finished",
            "usage_limit_exceeded",
            "out_of_quota",
        }:
            break
        await asyncio.sleep(interval)
    return [
        {k: v for k, v in row.items() if k != "body"} | {"body": row["body"]}
        for row in trail
    ]


def _trail_summary(trail: list[dict[str, Any]]) -> str:
    pairs: list[str] = []
    for row in trail:
        pair = f"{row.get('status')}/{row.get('status_detail')}"
        if not pairs or pairs[-1] != pair:
            pairs.append(pair)
    return " -> ".join(pairs) if pairs else "no samples"


def _trim_list(payload: Any) -> Any:
    if not isinstance(payload, dict) or "items" not in payload:
        return payload
    items = payload.get("items") or []
    trimmed = []
    for item in items[:2]:
        if isinstance(item, dict):
            trimmed.append(
                {
                    k: item.get(k)
                    for k in (
                        "session_id",
                        "playbook_id",
                        "note_id",
                        "secret_id",
                        "status",
                        "status_detail",
                        "created_at",
                        "updated_at",
                        "tags",
                        "title",
                        "name",
                        "key",
                        "is_archived",
                    )
                    if k in item
                }
            )
        else:
            trimmed.append(item)
    return {**payload, "items": trimmed}


def _list_note(status: int, payload: Any) -> dict[str, Any]:
    if status >= 400 or not isinstance(payload, dict):
        return {"status": status, "detail": _detail(payload)}
    items = payload.get("items") or []
    first = items[0] if items else {}
    created = first.get("created_at") if isinstance(first, dict) else None
    return {
        "status": status,
        "total": payload.get("total"),
        "item_count": len(items),
        "has_next_page": payload.get("has_next_page"),
        "end_cursor_null": payload.get("end_cursor") is None,
        "created_at": _epoch_unit(created) if created is not None else None,
        "keys": sorted(first.keys()) if isinstance(first, dict) else [],
    }


def _first_item(payload: Any) -> Any:
    if isinstance(payload, dict):
        items = payload.get("items") or []
        return items[0] if items else None
    return None


def _first_email(payload: Any) -> str | None:
    item = _first_item(payload)
    if isinstance(item, dict) and isinstance(item.get("email"), str):
        return item["email"]
    return None


def _item_ids(payload: Any) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    ids = set()
    for item in payload.get("items") or []:
        if isinstance(item, dict) and item.get("session_id"):
            ids.add(item["session_id"])
    return ids


def _session_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        value = payload.get("session_id") or payload.get("id")
        return str(value) if value else None
    return None


def _print_summary(results: dict[str, str], notes: dict[str, Any]) -> None:
    print("\nSummary:")
    for key, value in sorted(results.items()):
        print(f"  {key}: {value}")
    print("\nNotes:")
    print(json.dumps(_redact(notes), indent=2)[:4000])


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
