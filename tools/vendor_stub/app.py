from __future__ import annotations

import copy
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from tools.vendor_stub.match import condition_failures, find_best
from tools.vendor_stub.mock_repo import MockRepo
from tools.vendor_stub.models import MockResponse, PaginateRequest, Registration

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


def _build_response(raw: MockResponse, stub_base: str) -> Response:
    headers = {str(k): str(v) for k, v in raw.headers.items()}
    if "Link" in headers:
        headers["Link"] = _rewrite_link_header(headers["Link"], stub_base)
    if "link" in headers:
        headers["link"] = _rewrite_link_header(headers["link"], stub_base)

    body = raw.body
    if isinstance(body, (dict, list)):
        body = _rewrite_next_urls(copy.deepcopy(body), stub_base)
        return JSONResponse(content=body, status_code=raw.status, headers=headers)
    return Response(content=str(body), status_code=raw.status, headers=headers)


@mock_router.post("/register")
async def register(payload: Registration) -> dict[str, Any]:
    saved = MockRepo.add_registration(payload)
    return {"ok": True, "registration": saved.model_dump()}


@mock_router.post("/paginate")
async def paginate(payload: PaginateRequest, request: Request) -> dict[str, Any]:
    """
    Register a page sequence. Each page is a full registration-ish response.
    Shared match conditions live at the top level; pages go in `pages`.
    """
    responses = list(payload.pages)
    reg = Registration(
        **payload.model_dump(exclude={"pages"}),
        response=responses[0],
        times=responses,
    )
    saved = MockRepo.add_registration(reg)
    return {
        "ok": True,
        "registration": saved.model_dump(),
        "stub_base": _stub_base(request),
    }


@mock_router.post("/reset")
async def reset() -> dict[str, Any]:
    MockRepo.reset()
    return {"ok": True}


@mock_router.get("/unmatched")
async def unmatched() -> dict[str, Any]:
    return {"ok": True, "unmatched": MockRepo.get_unmatched()}


@mock_router.get("/calls")
async def calls() -> dict[str, Any]:
    return {"ok": True, "calls": MockRepo.get_call_log()}


@mock_router.get("/registrations")
async def registrations() -> dict[str, Any]:
    return {
        "ok": True,
        "registrations": [r.model_dump() for r in MockRepo.list_registrations()],
    }


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
    MockRepo.log_call(call)

    reg, failed = find_best(
        MockRepo.list_registrations(),
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
        regs = MockRepo.list_registrations()
        if regs:
            best = None
            best_failed: list[str] = []
            best_score = -1

            for candidate in regs:
                c_failed = condition_failures(
                    candidate,
                    method=method,
                    path=full_path,
                    query=query,
                    headers=headers,
                    body_text=body_text,
                )
                score = candidate.condition_count() - len(c_failed)
                if score > best_score:
                    best_score = score
                    best = {
                        "id": candidate.id,
                        "method": candidate.method,
                        "path": candidate.path or candidate.path_regex,
                    }
                    best_failed = c_failed
            entry["closest_registration"] = best
            entry["closest_failed_conditions"] = best_failed
        MockRepo.log_unmatched(entry)
        return JSONResponse(
            {
                "error": "unmatched",
                "failed_conditions": entry["closest_failed_conditions"],
            },
            status_code=501,
        )

    if isinstance(reg.times, list):
        nxt = MockRepo.next_sequence_response(reg)
        if nxt is None:
            entry = {
                **call,
                "reason": "times sequence exhausted",
                "registration_id": reg.id,
            }
            MockRepo.log_unmatched(entry)
            return JSONResponse(
                {"error": "unmatched", "reason": "times exhausted"}, status_code=501
            )
        return _build_response(nxt, stub_base)

    if isinstance(reg.times, int):
        if not MockRepo.bump_times_remaining(reg):
            entry = {
                **call,
                "reason": "times count exhausted",
                "registration_id": reg.id,
            }
            MockRepo.log_unmatched(entry)
            return JSONResponse(
                {"error": "unmatched", "reason": "times exhausted"}, status_code=501
            )

    return _build_response(reg.response, stub_base)
