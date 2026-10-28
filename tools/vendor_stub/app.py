from __future__ import annotations

import copy
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from tools.vendor_stub import store
from tools.vendor_stub.match import find_best

app = FastAPI(title="vendor-stub")
mock_router = APIRouter(prefix="/__mock")


def _stub_base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _rewrite_next_urls(payload: Any, stub_base: str) -> Any:
    """Point Link headers / JSON next fields at this stub."""
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            if (
                key in ("next", "next_url", "nextUrl")
                and isinstance(value, str)
                and value
            ):
                parsed = urlparse(value)
                out[key] = f"{stub_base}{parsed.path}" + (
                    f"?{parsed.query}" if parsed.query else ""
                )
            else:
                out[key] = _rewrite_next_urls(value, stub_base)
        return out
    if isinstance(payload, list):
        return [_rewrite_next_urls(item, stub_base) for item in payload]
    return payload


def _rewrite_link_header(link: str, stub_base: str) -> str:
    def repl(match: re.Match[str]) -> str:
        url = match.group(1)
        parsed = urlparse(url)
        rewritten = f"{stub_base}{parsed.path}" + (
            f"?{parsed.query}" if parsed.query else ""
        )
        return f"<{rewritten}>"

    return re.sub(r"<([^>]+)>", repl, link)


def _build_response(raw: dict[str, Any], stub_base: str) -> Response:
    status = int(raw.get("status", 200))
    headers = {str(k): str(v) for k, v in (raw.get("headers") or {}).items()}
    if "Link" in headers:
        headers["Link"] = _rewrite_link_header(headers["Link"], stub_base)
    if "link" in headers:
        headers["link"] = _rewrite_link_header(headers["link"], stub_base)

    body = raw.get("body", {})
    if isinstance(body, (dict, list)):
        body = _rewrite_next_urls(copy.deepcopy(body), stub_base)
        return JSONResponse(content=body, status_code=status, headers=headers)
    return Response(content=str(body), status_code=status, headers=headers)


@mock_router.post("/register")
async def register(payload: dict[str, Any]) -> dict[str, Any]:
    saved = store.add_registration(payload)
    return {"ok": True, "registration": saved}


@mock_router.post("/paginate")
async def paginate(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """
    Register a page sequence. Each page is a full registration-ish response.
    Shared match conditions live at the top level; pages go in `pages`.
    """
    pages: list[dict[str, Any]] = payload.get("pages") or []
    if not pages:
        return JSONResponse({"ok": False, "error": "pages required"}, status_code=400)

    base = {k: v for k, v in payload.items() if k != "pages"}
    # times-as-sequence: each match returns the next page response
    responses = []
    for page in pages:
        responses.append(
            {
                "status": page.get("status", 200),
                "body": page.get("body", {}),
                "headers": page.get("headers") or {},
            }
        )
    reg = {
        **base,
        "response": responses[0],
        "times": responses,
        "priority": base.get("priority", 10),
    }
    saved = store.add_registration(reg)
    return {"ok": True, "registration": saved, "stub_base": _stub_base(request)}


@mock_router.post("/reset")
async def reset() -> dict[str, Any]:
    store.reset()
    return {"ok": True}


@mock_router.get("/unmatched")
async def unmatched() -> dict[str, Any]:
    return {"ok": True, "unmatched": store.get_unmatched()}


@mock_router.get("/calls")
async def calls() -> dict[str, Any]:
    return {"ok": True, "calls": store.get_call_log()}


@mock_router.get("/registrations")
async def registrations() -> dict[str, Any]:
    return {"ok": True, "registrations": store.list_registrations()}


app.include_router(mock_router)


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def wildcard(request: Request, path: str) -> Response:
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8", errors="replace")
    method = request.method
    full_path = "/" + path if path else "/"
    query = {k: v for k, v in request.query_params.multi_items()}
    headers = dict(request.headers)

    call = {
        "method": method,
        "path": full_path,
        "query": query,
        "headers": {k: v for k, v in headers.items() if k.lower() != "authorization"},
        "body": body_text[:4000],
    }
    store.log_call(call)

    reg, failed = find_best(
        store.list_registrations(),
        method=method,
        path=full_path,
        query=query,
        headers=headers,
        body_text=body_text,
    )
    stub_base = _stub_base(request)

    if reg is None:
        entry = {
            **call,
            "closest_failed_conditions": failed,
            "closest_registration": None,
        }
        # attach closest for debugging
        regs = store.list_registrations()
        if regs:
            best = None
            best_failed: list[str] = []
            best_score = -1
            from tools.vendor_stub.match import condition_failures

            for candidate in regs:
                c_failed = condition_failures(
                    candidate,
                    method=method,
                    path=full_path,
                    query=query,
                    headers=headers,
                    body_text=body_text,
                )
                set_count = sum(
                    1
                    for key in (
                        "method",
                        "path",
                        "path_regex",
                        "query",
                        "headers",
                        "body_contains",
                        "body_field",
                    )
                    if candidate.get(key) is not None
                )
                score = set_count - len(c_failed)
                if score > best_score:
                    best_score = score
                    best = {
                        "id": candidate.get("id"),
                        "method": candidate.get("method"),
                        "path": candidate.get("path") or candidate.get("path_regex"),
                    }
                    best_failed = c_failed
            entry["closest_registration"] = best
            entry["closest_failed_conditions"] = best_failed
        store.log_unmatched(entry)
        return JSONResponse(
            {
                "error": "unmatched",
                "failed_conditions": entry["closest_failed_conditions"],
            },
            status_code=501,
        )

    times = reg.get("times")
    if isinstance(times, list):
        nxt = store.next_sequence_response(reg["id"], times)
        if nxt is None:
            entry = {
                **call,
                "reason": "times sequence exhausted",
                "registration_id": reg.get("id"),
            }
            store.log_unmatched(entry)
            return JSONResponse(
                {"error": "unmatched", "reason": "times exhausted"}, status_code=501
            )
        return _build_response(nxt, stub_base)

    if isinstance(times, int):
        if not store.bump_times_remaining(reg):
            entry = {
                **call,
                "reason": "times count exhausted",
                "registration_id": reg.get("id"),
            }
            store.log_unmatched(entry)
            return JSONResponse(
                {"error": "unmatched", "reason": "times exhausted"}, status_code=501
            )

    response_body = reg.get("response") or {}
    return _build_response(response_body, stub_base)
