from __future__ import annotations

import asyncio
import base64
import datetime as dt
import fnmatch
import hmac
import hashlib
import os
from typing import AsyncIterator, Optional

from fastapi import FastAPI, APIRouter, Request, Header, HTTPException
from port_ocean.context.ocean import ocean
from port_ocean.exceptions.context import PortOceanContextNotFoundError
import logging
logger = logging.getLogger("ocean.github")

MAX_FILE_BYTES = 64_000
MAX_CONTENT_CHARS = 16_000

def _secret(key: str) -> str:
    for attr in ("integration_secrets", "secrets"):
        store = getattr(ocean, attr, None)
        if isinstance(store, dict) and key in store:
            return store[key]
    env_key = f"OCEAN__INTEGRATION__SECRETS__{key.upper()}"
    val = os.getenv(env_key)
    if val:
        return val
    raise KeyError(f"missing secret: {key} (checked {attr} and env {env_key})")

from github_client import GithubClient

ISO8601 = "%Y-%m-%dT%H:%M:%SZ"

def _parse_iso(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, ISO8601).replace(tzinfo=dt.timezone.utc)

def _days_ago_iso(days: int) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime(ISO8601)

def _client() -> GithubClient:
    cfg = ocean.integration_config
    return GithubClient(
        token=_secret("github_token"),
        base_url=cfg.get("base_url", "https://api.github.com"),
        max_concurrency=int(cfg.get("max_concurrency", 8)),
    )

async def _iter_target_repos(client: GithubClient):
    cfg = ocean.integration_config or {}
    raw = (
        cfg.get("exclude_orgs")
        or cfg.get("excluded_orgs")
        or cfg.get("excludeOrganizations")
        or os.getenv("OCEAN__INTEGRATION__CONFIG__EXCLUDE_ORGS")
        or os.getenv("EXCLUDE_ORGS")
        or []
    )
    if isinstance(raw, str):
        try:
            import json
            raw = json.loads(raw)
        except Exception:
            raw = [s.strip() for s in raw.split(",") if s.strip()]
    exclude_orgs = {s.lower() for s in (raw or [])}
    include = {s.lower() for s in (cfg.get("include_repos") or [])}
    exclude = {s.lower() for s in (cfg.get("exclude_repos") or [])}
    orgs = cfg.get("organizations") or []
    logger.info(f"Exclude orgs (effective): {sorted(exclude_orgs)}")
    seen = set()

    async def _maybe_yield(repo: dict):
        owner = ((repo.get("owner") or {}).get("login") or "").lower()
        full = (repo.get("full_name") or repo.get("name") or "").lower()
        if not owner or not full:
            return
        if owner in exclude_orgs:
            logger.info(f"Skipping repo {full} (excluded org {owner})")
            return
        if include and full not in include:
            return
        if full in exclude or full in seen:
            return
        seen.add(full)
        yield repo

    if orgs:
        for org in orgs:
            async for repo in client.iter_org_repos(org):
                async for x in _maybe_yield(repo):
                    yield x
    else:
        async for repo in client.iter_user_repos():
            async for x in _maybe_yield(repo):
                yield x

BATCH_SIZE = 100
@ocean.on_resync(kind="repository")
async def resync_repositories(kind: str | None = None):
    client = _client()
    batch = []
    async for repo in _iter_target_repos(client):
        batch.append(repo)
        if len(batch) >= BATCH_SIZE:
            yield batch
            batch = []
    if batch:
        yield batch

@ocean.on_resync(kind="pull_request")
async def resync_pull_requests(kind: str | None = None):
    client = _client()
    state = (ocean.integration_config.get("pr_state") or "").lower() or None
    days = ocean.integration_config.get("pr_updated_since_days")
    since_iso = None
    if isinstance(days, int) and days > 0:
        from datetime import datetime, timezone, timedelta
        since_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    batch = []
    async for repo in _iter_target_repos(client):
        async for pr in client.iter_pull_requests(
            owner=repo["owner"]["login"],
            repo=repo["name"],
            state=state,
            updated_since_iso=since_iso,
        ):
            pr["repo"] = {
                "name": repo["name"],
                "html_url": repo["html_url"],
                "default_branch": repo["default_branch"],
            }
            batch.append(pr)
            if len(batch) >= BATCH_SIZE:
                yield batch
                batch = []
    if batch:
        yield batch

@ocean.on_resync(kind="issue")
async def resync_issues(kind: str | None = None):
    client = _client()
    state = (ocean.integration_config.get("issue_state") or "").lower() or None
    days = ocean.integration_config.get("issue_updated_since_days")
    since_iso = None
    if isinstance(days, int) and days > 0:
        from datetime import datetime, timedelta, timezone
        since_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    batch = []
    async for repo in _iter_target_repos(client):
        async for issue in client.iter_issues(
            owner=repo["owner"]["login"],
            repo=repo["name"],
            state=state,
            updated_since_iso=since_iso,
        ):
            if "pull_request" in issue:
                continue
            issue["repo"] = {"name": repo["name"]}
            batch.append(issue)
            if len(batch) >= BATCH_SIZE:
                yield batch
                batch = []
    if batch:
        yield batch

@ocean.on_resync(kind="file")
async def resync_files(kind: str | None = None):
    client = _client()
    cfg = ocean.integration_config or {}
    globs = cfg.get("file_globs") or ["**/*.yaml","**/*.yml","**/*.json","**/*.md","**/*.py"]
    branch = cfg.get("file_branch") or None
    max_per_repo: int = int(cfg.get("file_max_per_repo", 1500))
    max_total: int = int(cfg.get("file_max_total", 15_000))
    skip_if_size_over: int = int(cfg.get("file_skip_if_size_over_bytes", 256_000))
    MAX_FILE_BYTES = int(cfg.get("file_truncate_if_over_bytes", 64_000))
    MAX_CONTENT_CHARS = int(cfg.get("file_max_content_chars", 16_000))
    log_every_n = int(cfg.get("file_log_every_n", 500))
    processed_total = 0
    batch = []

    async for repo in _iter_target_repos(client):
        processed_repo = 0
        repo_name = repo["name"]
        if processed_total >= max_total:
            logger.info(f"[files] Reached global cap ({processed_total}/{max_total}). Stopping.")
            break
        try:
            async for f in client.iter_repo_files(
                owner=repo["owner"]["login"],
                repo=repo_name,
                globs=globs,
                branch=branch or repo.get("default_branch"),
            ):
                if processed_total >= max_total:
                    logger.info(f"[files] Reached global cap ({processed_total}/{max_total}). Stopping.")
                    break
                if processed_repo >= max_per_repo:
                    logger.info(f"[files] Reached per-repo cap for {repo_name} ({processed_repo}/{max_per_repo}). Moving on.")
                    break
                size = f.get("size") or 0
                if isinstance(size, int) and size > skip_if_size_over:
                    continue
                try:
                    if isinstance(size, int) and size > MAX_FILE_BYTES:
                        f.pop("content", None)
                        f.pop("contentPreview", None)
                    else:
                        content = f.get("content") or f.get("contentPreview")
                        if isinstance(content, str) and len(content) > MAX_CONTENT_CHARS:
                            trimmed = content[:MAX_CONTENT_CHARS] + "...(truncated)"
                            f["content"] = trimmed
                            f["contentPreview"] = trimmed
                except Exception as e:
                    logger.warning(f"[files] Failed to cap content for {repo_name}:{f.get('path')}: {e}")
                f["repo"] = {"name": repo_name}
                batch.append(f)
                processed_repo += 1
                processed_total += 1
                if processed_repo % log_every_n == 0:
                    logger.info(f"[files] {repo_name}: processed {processed_repo} files (global {processed_total}/{max_total})")
                if len(batch) >= BATCH_SIZE:
                    yield batch
                    batch = []
        except Exception as e:
            full = repo.get("full_name") or repo_name
            logger.warning(f"[files] Skipping repo {full} due to error: {e}")
        if batch:
            yield batch
            batch = []
    if batch:
        yield batch

router = APIRouter()

def _gh_secret() -> bytes:
    return _secret("github_webhook_secret").encode("utf-8")

def _verify_sig(sig_header: str | None, body: bytes) -> None:
    if not sig_header or not sig_header.startswith("sha256="):
        raise HTTPException(status_code=400, detail="Missing or bad signature")
    theirs = sig_header.split("=", 1)[1]
    ours = hmac.new(_gh_secret(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(theirs, ours):
        raise HTTPException(status_code=401, detail="Bad signature")

async def _upsert_entities(kind: str, items: list[dict]):
    if hasattr(ocean, "emit"):
        await ocean.emit(kind=kind, items=items)
        return
    if hasattr(ocean, "register_raw"):
        await ocean.register_raw(kind, items)
        return
    raise RuntimeError("No upsert method available on ocean context")

async def _handle_pr_event(payload: dict):
    repo = payload["repository"]["name"]
    owner = payload["repository"]["owner"]["login"]
    number = payload["number"] if "number" in payload else payload["pull_request"]["number"]
    client = _client()
    base = client.base_url
    pr = await client._request("GET", f"{base}/repos/{owner}/{repo}/pulls/{number}")
    pr["repo"] = {"name": repo}
    await _upsert_entities("pull_request", [pr])

async def _handle_issue_event(payload: dict):
    repo = payload["repository"]["name"]
    owner = payload["repository"]["owner"]["login"]
    number = payload["issue"]["number"]
    client = _client()
    base = client.base_url
    issue = await client._request("GET", f"{base}/repos/{owner}/{repo}/issues/{number}")
    if "pull_request" in issue:
        return
    issue["repo"] = {"name": repo}
    await _upsert_entities("issue", [issue])

async def _handle_push_event(payload: dict):
    repo_info = payload.get("repository")
    if not isinstance(repo_info, dict):
        return

    repo = repo_info.get("name")
    owner_info = repo_info.get("owner") or {}
    owner = owner_info.get("login")
    if not repo or not owner:
        return

    ref = (payload.get("ref") or "").split("/")[-1] or repo_info.get("default_branch") or "main"

    client = _client()
    cfg = ocean.integration_config or {}
    globs = cfg.get("file_globs") or ["**/*.yaml","**/*.yml","**/*.json","**/*.md","**/*.py"]

    items = []
    async for f in client.iter_repo_files(owner=owner, repo=repo, globs=globs, branch=ref):
        size = f.get("size") or 0
        if isinstance(size, int) and size > int(cfg.get("file_skip_if_size_over_bytes", 256_000)):
            continue
        max_bytes = int(cfg.get("file_truncate_if_over_bytes", 64_000))
        max_chars = int(cfg.get("file_max_content_chars", 16_000))
        if isinstance(size, int) and size > max_bytes:
            f.pop("content", None)
            f.pop("contentPreview", None)
        else:
            content = f.get("content") or f.get("contentPreview")
            if isinstance(content, str) and len(content) > max_chars:
                trimmed = content[:max_chars] + "...(truncated)"
                f["content"] = trimmed
                f["contentPreview"] = trimmed
        f["repo"] = {"name": repo}
        items.append(f)
        if len(items) >= 200:
            await _upsert_entities("file", items)
            items = []
    if items:
        await _upsert_entities("file", items)

async def _handle_repository_event(payload: dict):
    repo = payload["repository"]["name"]
    owner = payload["repository"]["owner"]["login"]
    client = _client()
    base = client.base_url
    r = await client._request("GET", f"{base}/repos/{owner}/{repo}")
    await _upsert_entities("repository", [r])

@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
):
    raw = await request.body()

    if not x_hub_signature_256:
        raise HTTPException(status_code=400, detail="Missing signature")

    _verify_sig(x_hub_signature_256, raw)

    if not x_github_event:
        return {"ok": True}

    payload = await request.json()

    if x_github_event == "pull_request":
        await _handle_pr_event(payload)
    elif x_github_event == "issues":
        await _handle_issue_event(payload)
    elif x_github_event == "push":
        await _handle_push_event(payload)
    elif x_github_event in ("repository", "installation_repositories"):
        await _handle_repository_event(payload)

    return {"ok": True}

def _get_fastapi_app():
    fa = getattr(ocean, "http_app", None)
    if fa is None:
        ocean_obj = getattr(ocean, "app", None)
        if ocean_obj is not None and hasattr(ocean_obj, "http_app"):
            fa = ocean_obj.http_app
    if fa is None:
        fa = FastAPI()
    return fa

def _attach_router_safely():
    try:
        fa = _get_fastapi_app()
        fa.include_router(router)
        return fa
    except PortOceanContextNotFoundError:
        fa = FastAPI()
        fa.include_router(router)
        return fa

if os.getenv("PORT_OCEAN_ATTACH_ROUTER", "1") != "0":
    _fa = _attach_router_safely()
else:
    _fa = _get_fastapi_app()

if os.getenv("PORT_OCEAN_SKIP_REG", "0") != "1":
    _register_handlers()


if os.getenv("PYTEST_CURRENT_TEST"):
    app = _fa
else:
    app = ocean.app 