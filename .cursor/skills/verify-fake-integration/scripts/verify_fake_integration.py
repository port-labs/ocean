#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PORT = 8000
SYNC_TIMEOUT_SECONDS = 180
SERVE_TIMEOUT_SECONDS = 90
CLOCK_SKEW = timedelta(seconds=5)

KINDS: dict[str, dict[str, str | None]] = {
    "fake-department": {
        "blueprint": "fake-department",
        "route": None,
        "shape": "departments",
    },
    "fake-person": {
        "blueprint": "fake-person",
        "route": "/integration/department/hr/employees?limit=1&entity_kb_size=1&latency=0",
        "shape": "persons",
    },
    "fake-office": {
        "blueprint": "fake-office",
        "route": "/integration/offices",
        "shape": "offices",
    },
    "fake-team": {
        "blueprint": "fake-team",
        "route": "/integration/teams",
        "shape": "teams",
    },
    "fake-project": {
        "blueprint": "fake-project",
        "route": "/integration/projects",
        "shape": "projects",
    },
}

_ENV: dict[str, str] | None = None
_TOKEN: str | None = None


class ApiError(Exception):
    def __init__(self, method: str, path: str, status: int, body: str) -> None:
        super().__init__(f"{method} {path} returned {status}")
        self.method = method
        self.path = path
        self.status = status
        self.body = body


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        marker = parent / "integrations" / "fake-integration" / "pyproject.toml"
        if marker.is_file():
            return parent
    raise SystemExit(
        "This script must live inside the ocean repo. "
        "Could not find integrations/fake-integration/pyproject.toml."
    )


def integration_dir() -> Path:
    return repo_root() / "integrations" / "fake-integration"


def verify_dir() -> Path:
    return integration_dir() / ".verify"


def venv_python() -> Path:
    return integration_dir() / ".venv" / "bin" / "python"


def ocean_bin() -> Path:
    return integration_dir() / ".venv" / "bin" / "ocean"


def read_env() -> dict[str, str]:
    global _ENV
    if _ENV is not None:
        return _ENV
    path = integration_dir() / ".env"
    if not path.is_file():
        raise SystemExit(
            f"Missing {path}. Copy .env.example and point it at the local Port API."
        )
    parsed: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :]
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        parsed[key] = value
    _ENV = parsed
    return parsed


def require_env() -> dict[str, str]:
    env = read_env()
    missing = [
        key
        for key in (
            "OCEAN__PORT__CLIENT_ID",
            "OCEAN__PORT__CLIENT_SECRET",
            "OCEAN__PORT__BASE_URL",
            "OCEAN__INTEGRATION__IDENTIFIER",
        )
        if not env.get(key)
    ]
    if missing:
        raise SystemExit(
            "Active .env lines are missing: "
            + ", ".join(missing)
            + ". Commented lines are ignored."
        )
    return env


def integration_identifier() -> str:
    return require_env()["OCEAN__INTEGRATION__IDENTIFIER"]


def emit(payload: dict[str, Any], evidence: Path | None = None) -> None:
    if evidence is not None:
        evidence.mkdir(parents=True, exist_ok=True)
        summary = evidence / "summary.json"
        payload = {**payload, "evidence": str(summary)}
        summary.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    raise SystemExit(0 if payload.get("ok") else 1)


def new_evidence(command: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = verify_dir() / "evidence" / f"{stamp}-{command}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def access_token() -> str:
    global _TOKEN
    if _TOKEN:
        return _TOKEN
    env = require_env()
    url = env["OCEAN__PORT__BASE_URL"].rstrip("/") + "/v1/auth/access_token"
    payload = {
        "clientId": env["OCEAN__PORT__CLIENT_ID"],
        "clientSecret": env["OCEAN__PORT__CLIENT_SECRET"],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:300]
        raise SystemExit(
            f"Port token request failed with {error.code}: {detail}"
        ) from error
    token = body.get("accessToken")
    if not token:
        raise SystemExit("Port token response had no accessToken.")
    _TOKEN = token
    return token


def api(
    method: str, path: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    env = require_env()
    url = env["OCEAN__PORT__BASE_URL"].rstrip("/") + "/v1" + path
    data = None if payload is None else json.dumps(payload).encode()
    headers = {
        "Authorization": f"Bearer {access_token()}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return json.loads(raw.decode()) if raw else {}
    except urllib.error.HTTPError as error:
        raise ApiError(
            method,
            path,
            error.code,
            error.read().decode(errors="replace")[:500],
        ) from error


def local_get(path: str) -> tuple[int, dict[str, Any] | str]:
    url = f"http://127.0.0.1:{PORT}{path}"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode()
            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, raw[:300]
    except urllib.error.HTTPError as error:
        raw = error.read().decode(errors="replace")
        try:
            parsed: dict[str, Any] | str = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw[:300]
        return error.code, parsed
    except urllib.error.URLError as error:
        return 0, {"detail": str(error.reason)}


def listener_pid() -> int | None:
    result = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{PORT}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = [int(line) for line in result.stdout.split() if line.strip().isdigit()]
    return pids[0] if pids else None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def command_of(pid: int) -> str:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def is_sail_command(command: str) -> bool:
    return "sail" in command or "port_ocean" in command or "ocean" in command


def record_path(name: str) -> Path:
    return verify_dir() / f"{name}.json"


def read_record(name: str) -> dict[str, Any] | None:
    path = record_path(name)
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def write_record(name: str, payload: dict[str, Any]) -> None:
    verify_dir().mkdir(parents=True, exist_ok=True)
    record_path(name).write_text(json.dumps(payload, indent=2) + "\n")


def clear_record(name: str) -> None:
    path = record_path(name)
    if path.exists():
        path.unlink()


def our_pids() -> set[int]:
    pids: set[int] = set()
    for name in ("sync", "serve"):
        record = read_record(name)
        if not record:
            continue
        pid = int(record["pid"])
        if pid_alive(pid):
            pids.add(pid)
        else:
            clear_record(name)
    return pids


def kill_group(pid: int) -> None:
    if not pid_alive(pid):
        return
    command = command_of(pid)
    if command and not is_sail_command(command):
        raise SystemExit(
            f"Refusing to signal pid {pid}. Its command is not ocean sail: {command}"
        )
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + 10
    while time.time() < deadline and pid_alive(pid):
        time.sleep(0.2)
    if pid_alive(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            return


def port_ocean_status() -> dict[str, Any]:
    python = venv_python()
    if not python.is_file() or not ocean_bin().is_file():
        return {
            "ok": False,
            "detail": "Missing .venv. From integrations/fake-integration run make install and make install/local-core.",
        }
    result = subprocess.run(
        [
            str(python),
            "-c",
            (
                "import pathlib, port_ocean; "
                "print(port_ocean.__version__); "
                "print(pathlib.Path(port_ocean.__file__).resolve())"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {"ok": False, "detail": result.stderr[-400:]}
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return {"ok": False, "detail": "Could not read port_ocean version."}
    location = Path(lines[1])
    inside = repo_root() in location.parents or location.is_relative_to(repo_root())
    return {
        "ok": inside,
        "version": lines[0],
        "file": str(location),
        "detail": (
            None
            if inside
            else "port_ocean is not this checkout. Run make install/local-core."
        ),
    }


def get_integration() -> tuple[dict[str, Any] | None, int]:
    identifier = urllib.parse.quote(integration_identifier(), safe="")
    try:
        payload = api("GET", f"/integration/{identifier}")
    except ApiError as error:
        if error.status == 404:
            return None, 404
        raise
    return payload.get("integration") or {}, 200


def literal_blueprint(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if value[0] == '"' and value[-1] == '"':
        inner = value[1:-1]
        return inner or None
    if value.startswith(".") or any(token in value for token in ("|", "(", " ")):
        return None
    return value


def blueprint_of(resource: dict[str, Any]) -> str | None:
    mappings = resource.get("port", {}).get("entity", {}).get("mappings")
    if isinstance(mappings, list):
        mappings = mappings[0] if mappings else None
    if not isinstance(mappings, dict):
        return None
    return literal_blueprint(mappings.get("blueprint"))


def entity_rows(blueprint: str) -> list[dict[str, Any]]:
    quoted = urllib.parse.quote(blueprint, safe="")
    payload = api("GET", f"/blueprints/{quoted}/entities")
    entities = payload.get("entities") or []
    return entities if isinstance(entities, list) else []


def parse_port_time(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def log_tail(path: Path, lines: int = 40) -> list[str]:
    if not path.is_file():
        return []
    content = path.read_text(errors="replace").splitlines()
    return content[-lines:]


def log_notes(path: Path) -> dict[str, bool]:
    text = path.read_text(errors="replace") if path.is_file() else ""
    return {
        "dsp_fallback": "falling back to ocean-core" in text,
        "log_pickling_error": "PicklingError" in text,
    }


def launch_env(extra: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(require_env())
    env.update(extra)
    return env


def port_blocked_by_foreign() -> str | None:
    owner = listener_pid()
    if owner is None:
        return None
    if owner in our_pids():
        return (
            f"Port {PORT} is already used by verify pid {owner}. "
            "Run stop before starting another sail."
        )
    return (
        f"Port {PORT} is owned by pid {owner}, which this skill did not start. "
        "fake_client.py calls http://localhost:8000, so do not move the port."
    )


def run_sail(
    evidence: Path,
    extra_env: dict[str, str],
    record_name: str | None,
) -> tuple[subprocess.Popen[bytes], Path]:
    blocked = port_blocked_by_foreign()
    if blocked:
        raise SystemExit(blocked)
    log_path = evidence / "sail.log"
    handle = log_path.open("w")
    try:
        process = subprocess.Popen(
            [str(ocean_bin()), "sail", "."],
            cwd=integration_dir(),
            env=launch_env(extra_env),
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        handle.close()
    if record_name:
        write_record(
            record_name,
            {
                "pid": process.pid,
                "log": str(log_path),
                "evidence": str(evidence),
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    return process, log_path


def wait_process(process: subprocess.Popen[bytes], timeout: int) -> int:
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_group(process.pid)
        try:
            return process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            return 124


def resync_ok(started_at: datetime) -> tuple[bool, dict[str, Any]]:
    integration, status = get_integration()
    if integration is None:
        return False, {"http_status": status, "detail": "Integration was not created."}
    state = integration.get("resyncState") or {}
    end = state.get("lastResyncEnd")
    start = state.get("lastResyncStart")
    completed = state.get("status") == "completed"
    fresh = False
    if isinstance(start, str) and isinstance(end, str):
        fresh = (
            parse_port_time(start) >= started_at - CLOCK_SKEW
            and parse_port_time(end) >= started_at - CLOCK_SKEW
        )
    return completed and fresh, state


def count_configured_entities(integration: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, Any] = {}
    ok = True
    for resource in integration.get("config", {}).get("resources") or []:
        kind = resource.get("kind")
        blueprint = blueprint_of(resource) if isinstance(resource, dict) else None
        if not isinstance(kind, str) or blueprint is None:
            ok = False
            counts[str(kind)] = {"blueprint": blueprint, "count": None}
            continue
        try:
            rows = entity_rows(blueprint)
        except ApiError as error:
            ok = False
            counts[kind] = {
                "blueprint": blueprint,
                "error": error.status,
                "body": error.body,
            }
            continue
        counts[kind] = {"blueprint": blueprint, "count": len(rows)}
        if len(rows) < 1:
            ok = False
    return {"ok": ok, "kinds": counts}


def command_doctor() -> None:
    env = require_env()
    core = port_ocean_status()
    integration: dict[str, Any] | None = None
    integration_status = None
    token_ok = False
    token_error = None
    try:
        access_token()
        token_ok = True
        integration, integration_status = get_integration()
    except (SystemExit, ApiError) as error:
        token_error = str(error)
    owner = listener_pid()
    ours = our_pids()
    foreign = owner is not None and owner not in ours
    health: dict[str, Any] | None = None
    if owner is not None and owner in ours:
        status, body = local_get("/health/ready")
        health = {"status_code": status, "body": body}
    ok = bool(core.get("ok") and token_ok and not foreign)
    emit(
        {
            "ok": ok,
            "integration_identifier": env["OCEAN__INTEGRATION__IDENTIFIER"],
            "base_url": env["OCEAN__PORT__BASE_URL"],
            "integration_exists": integration is not None,
            "integration_http_status": integration_status,
            "resync": None if integration is None else integration.get("resyncState"),
            "port": PORT,
            "listener_pid": owner,
            "listener": "foreign" if foreign else "ours" if owner in ours else "free",
            "health": health,
            "port_ocean": core,
            "token_ok": token_ok,
            "token_error": token_error,
        }
    )


def finish_sync(
    evidence: Path,
    started_at: datetime,
    exit_code: int,
    log_path: Path,
) -> None:
    clear_record("sync")
    fresh, state = resync_ok(started_at)
    integration, _status = get_integration()
    counts = (
        count_configured_entities(integration)
        if integration is not None
        else {"ok": False, "kinds": {}}
    )
    ok = exit_code == 0 and fresh and bool(counts.get("ok"))
    payload: dict[str, Any] = {
        "ok": ok,
        "command": "sync",
        "started_at": started_at.isoformat(),
        "exit_code": exit_code,
        "resync": state,
        "resync_is_new": fresh,
        "entity_counts": counts["kinds"],
        "log": str(log_path),
        "log_notes": log_notes(log_path),
    }
    if not ok:
        payload["log_tail"] = log_tail(log_path)
    emit(payload, evidence)


def command_sync(timeout: int) -> None:
    if not ocean_bin().is_file():
        raise SystemExit(
            "Missing .venv ocean. Run make install and make install/local-core."
        )
    evidence = new_evidence("sync")
    started_at = datetime.now(timezone.utc)
    process, log_path = run_sail(evidence, {}, "sync")
    exit_code = wait_process(process, timeout)
    finish_sync(evidence, started_at, exit_code, log_path)


def command_serve(timeout: int) -> None:
    if not ocean_bin().is_file():
        raise SystemExit(
            "Missing .venv ocean. Run make install and make install/local-core."
        )
    evidence = new_evidence("serve")
    extra = {
        "OCEAN__EVENT_LISTENER__TYPE": "POLLING",
        "OCEAN__EVENT_LISTENER__RESYNC_ON_START": "false",
        "OCEAN__EVENT_LISTENER__INTERVAL": "3600",
    }
    process, log_path = run_sail(evidence, extra, "serve")
    deadline = time.time() + timeout
    health: dict[str, Any] | None = None
    while time.time() < deadline:
        if process.poll() is not None:
            clear_record("serve")
            emit(
                {
                    "ok": False,
                    "command": "serve",
                    "exit_code": process.returncode,
                    "log": str(log_path),
                    "log_tail": log_tail(log_path),
                    "detail": "ocean sail exited before /health/ready.",
                },
                evidence,
            )
        status, body = local_get("/health/ready")
        health = {"status_code": status, "body": body}
        if status == 200 and isinstance(body, dict) and body.get("status") == "healthy":
            emit(
                {
                    "ok": True,
                    "command": "serve",
                    "pid": process.pid,
                    "health": health,
                    "log": str(log_path),
                    "detail": "Routes are on port 8000. A pending Port resync request can still start a resync on the first poll.",
                },
                evidence,
            )
        time.sleep(1)
    kill_group(process.pid)
    clear_record("serve")
    emit(
        {
            "ok": False,
            "command": "serve",
            "health": health,
            "log": str(log_path),
            "log_tail": log_tail(log_path),
            "detail": f"/health/ready did not become healthy within {timeout}s.",
        },
        evidence,
    )


def command_stop() -> None:
    stopped: list[int] = []
    for name in ("serve", "sync"):
        record = read_record(name)
        if not record:
            continue
        pid = int(record["pid"])
        if pid_alive(pid):
            kill_group(pid)
            stopped.append(pid)
        clear_record(name)
    emit(
        {
            "ok": True,
            "command": "stop",
            "signaled_pids": stopped,
            "evidence_dir": str(verify_dir() / "evidence"),
            "detail": "Evidence files were left in place. The Port integration and catalog were not deleted.",
        }
    )


def command_routes() -> None:
    evidence = new_evidence("routes")
    status, body = local_get("/health/ready")
    if status != 200 or not isinstance(body, dict) or body.get("status") != "healthy":
        emit(
            {
                "ok": False,
                "command": "routes",
                "health": {"status_code": status, "body": body},
                "detail": "Run serve and wait for doctor health status healthy before routes.",
            },
            evidence,
        )
    checks = []
    ok = True
    for kind, meta in KINDS.items():
        route = meta["route"]
        if not route:
            checks.append({"kind": kind, "route": None, "skipped": True})
            continue
        code, payload = local_get(route)
        results = payload.get("results") if isinstance(payload, dict) else None
        count = len(results) if isinstance(results, list) else 0
        passed = code == 200 and count > 0
        ok = ok and passed
        sample_id = None
        if isinstance(results, list) and results and isinstance(results[0], dict):
            sample_id = results[0].get("id")
        checks.append(
            {
                "kind": kind,
                "route": route,
                "status_code": code,
                "count": count,
                "sample_id": sample_id,
                "ok": passed,
            }
        )
    emit({"ok": ok, "command": "routes", "checks": checks}, evidence)


def produce_shapes(kind: str, count: int) -> list[dict[str, Any]]:
    meta = KINDS.get(kind)
    if meta is None:
        raise SystemExit(
            f"Unknown kind {kind}. Pass --file with a JSON list, or use one of: "
            + ", ".join(KINDS)
        )
    sys.path.insert(0, str(integration_dir()))
    shape = meta["shape"]
    if shape == "persons":
        from fake_org_data.generator import generate_fake_persons
        import asyncio

        payload = asyncio.run(generate_fake_persons("hr", count, 1, 0))
        return list(payload["results"])
    if shape == "projects":
        from fake_org_data.generator import generate_fake_projects
        import asyncio

        payload = asyncio.run(generate_fake_projects(count))
        return list(payload["results"])
    from fake_org_data.static import FAKE_DEPARTMENTS, FAKE_OFFICES, FAKE_TEAMS

    source = {
        "departments": FAKE_DEPARTMENTS,
        "offices": FAKE_OFFICES,
        "teams": FAKE_TEAMS,
    }[str(shape)]
    return [item.dict() for item in source[:count]]


def load_example_file(path: Path, count: int) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    if isinstance(payload, dict) and isinstance(payload.get("examples"), list):
        payload = payload["examples"]
    if not isinstance(payload, list):
        raise SystemExit(
            "--file must be a JSON list or an object with an examples list."
        )
    examples = payload[:count]
    if not examples or not all(isinstance(item, dict) for item in examples):
        raise SystemExit("--file examples must be a non-empty list of objects.")
    return examples


def command_shapes(kind: str, count: int, file_path: str | None, post: bool) -> None:
    evidence = new_evidence("shapes")
    if count < 1:
        raise SystemExit("--count must be at least 1.")
    if file_path:
        examples = load_example_file(Path(file_path), count)
        source = "file"
    else:
        examples = produce_shapes(kind, count)
        source = KINDS[kind]["shape"]
    posted = False
    found = None
    if post:
        identifier = urllib.parse.quote(integration_identifier(), safe="")
        quoted_kind = urllib.parse.quote(kind, safe="")
        api(
            "POST",
            f"/integration/{identifier}/kinds/{quoted_kind}/examples",
            {"examples": examples},
        )
        posted = True
        kinds = api("GET", f"/integration/{identifier}/kinds")
        stored = (kinds.get("data") or {}).get(kind, {}).get("examples") or []
        stored_data = [
            item.get("data")
            for item in stored
            if isinstance(item, dict) and isinstance(item.get("data"), dict)
        ]
        found = all(example in stored_data for example in examples)
    ids = [item.get("id") for item in examples]
    keys = sorted(examples[0].keys()) if examples else []
    ok = (not post) or found is True
    emit(
        {
            "ok": ok,
            "command": "shapes",
            "kind": kind,
            "source": source,
            "ids": ids,
            "keys": keys,
            "examples": examples,
            "posted": posted,
            "posted_examples_found": found,
        },
        evidence,
    )


def backup_path() -> Path:
    return verify_dir() / "state" / "mapping-backup.json"


def current_config() -> dict[str, Any]:
    integration, _status = get_integration()
    if integration is None:
        raise SystemExit(
            f"Integration {integration_identifier()} does not exist yet. Run sync before changing its mapping."
        )
    config = integration.get("config")
    if not isinstance(config, dict):
        raise SystemExit("Integration config was not an object.")
    return config


def save_backup_once(config: dict[str, Any]) -> bool:
    path = backup_path()
    if path.is_file():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")
    return True


def patch_config(config: dict[str, Any]) -> None:
    identifier = urllib.parse.quote(integration_identifier(), safe="")
    api("PATCH", f"/integration/{identifier}/config", {"config": config})


def parse_maps(pairs: list[str]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--map value must be key=jq, got {pair}")
        key, value = pair.split("=", 1)
        if not key or not value:
            raise SystemExit(f"--map value must be key=jq, got {pair}")
        updates[key] = value
    return updates


def apply_maps(resource: dict[str, Any], updates: dict[str, str]) -> None:
    mappings = resource.get("port", {}).get("entity", {}).get("mappings")
    targets = mappings if isinstance(mappings, list) else [mappings]
    if not targets or any(not isinstance(target, dict) for target in targets):
        raise SystemExit(
            f"Resource {resource.get('kind')} has no mapping object to update."
        )
    for target in targets:
        target.update(updates)


def load_mapping_file(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    if isinstance(payload, list):
        resources = payload
    elif isinstance(payload, dict) and isinstance(payload.get("resources"), list):
        resources = payload["resources"]
    elif isinstance(payload, dict) and "kind" in payload:
        resources = [payload]
    else:
        raise SystemExit(
            "--file must be one resource object, a list of resources, or an object with resources."
        )
    if not resources or any(
        not isinstance(item, dict) or "kind" not in item for item in resources
    ):
        raise SystemExit("Each mapping resource needs a kind.")
    return resources


def merge_resources(
    config: dict[str, Any], incoming: list[dict[str, Any]]
) -> tuple[list[str], list[str]]:
    resources = list(config.get("resources") or [])
    index = {
        resource.get("kind"): position for position, resource in enumerate(resources)
    }
    replaced: list[str] = []
    appended: list[str] = []
    for resource in incoming:
        kind = resource["kind"]
        if kind in index:
            resources[index[kind]] = resource
            replaced.append(str(kind))
        else:
            index[kind] = len(resources)
            resources.append(resource)
            appended.append(str(kind))
    config["resources"] = resources
    return replaced, appended


def command_mapping_show(kind: str) -> None:
    config = current_config()
    matches = [
        resource
        for resource in config.get("resources") or []
        if isinstance(resource, dict) and resource.get("kind") == kind
    ]
    if not matches:
        emit(
            {
                "ok": False,
                "command": "mapping show",
                "kind": kind,
                "detail": "That kind is not in the integration config.",
            }
        )
    emit({"ok": True, "command": "mapping show", "kind": kind, "resource": matches[-1]})


def command_mapping_apply(
    file_path: str | None,
    kind: str | None,
    maps: list[str],
    run: bool,
    timeout: int,
) -> None:
    evidence = new_evidence("mapping-apply")
    if file_path and (kind or maps):
        raise SystemExit("Use either --file or --kind with --map, not both.")
    if run:
        blocked = port_blocked_by_foreign()
        if blocked:
            raise SystemExit(blocked)
    original = current_config()
    backup_created = save_backup_once(original)
    updated = copy.deepcopy(original)
    if file_path:
        incoming = load_mapping_file(Path(file_path))
    elif kind and maps:
        matches = [
            resource
            for resource in updated.get("resources") or []
            if isinstance(resource, dict) and resource.get("kind") == kind
        ]
        if not matches:
            raise SystemExit(
                f"{kind} is not in the config. Add it with --file. A kind also needs @ocean.on_resync in integration.py before sail can emit it."
            )
        apply_maps(matches[-1], parse_maps(maps))
        incoming = [matches[-1]]
    else:
        raise SystemExit("Pass --file, or --kind and at least one --map key=jq.")
    replaced, appended = merge_resources(updated, incoming)
    patch_config(updated)
    payload: dict[str, Any] = {
        "ok": True,
        "command": "mapping apply",
        "backup_created": backup_created,
        "backup": str(backup_path()),
        "replaced": replaced,
        "appended": appended,
        "ran": False,
    }
    if not run:
        emit(payload, evidence)
    exit_code = None
    try:
        started_at = datetime.now(timezone.utc)
        process, log_path = run_sail(evidence, {}, "sync")
        exit_code = wait_process(process, timeout)
        fresh, state = resync_ok(started_at)
        payload["ran"] = True
        payload["exit_code"] = exit_code
        payload["resync"] = state
        payload["resync_is_new"] = fresh
        payload["log"] = str(log_path)
        payload["log_notes"] = log_notes(log_path)
        payload["ok"] = exit_code == 0 and fresh
        if not payload["ok"]:
            payload["log_tail"] = log_tail(log_path)
    finally:
        clear_record("sync")
    emit(payload, evidence)


def command_mapping_restore(run: bool, timeout: int) -> None:
    evidence = new_evidence("mapping-restore")
    path = backup_path()
    if not path.is_file():
        emit(
            {
                "ok": False,
                "command": "mapping restore",
                "detail": "No mapping backup. apply saves one on the first change.",
            },
            evidence,
        )
    if run:
        blocked = port_blocked_by_foreign()
        if blocked:
            raise SystemExit(blocked)
    config = json.loads(path.read_text())
    patch_config(config)
    path.unlink()
    payload: dict[str, Any] = {
        "ok": True,
        "command": "mapping restore",
        "ran": False,
        "detail": "Config patched back. Catalog entities still show the scenario mapping until a sail completes.",
    }
    if not run:
        emit(payload, evidence)
    started_at = datetime.now(timezone.utc)
    process, log_path = run_sail(evidence, {}, "sync")
    exit_code = wait_process(process, timeout)
    clear_record("sync")
    fresh, state = resync_ok(started_at)
    payload.update(
        {
            "ran": True,
            "exit_code": exit_code,
            "resync": state,
            "resync_is_new": fresh,
            "log": str(log_path),
            "log_notes": log_notes(log_path),
            "ok": exit_code == 0 and fresh,
        }
    )
    if not payload["ok"]:
        payload["log_tail"] = log_tail(log_path)
    emit(payload, evidence)


def command_entities(
    blueprint: str,
    limit: int,
    title_suffix: str | None,
    title_suffix_absent: str | None,
) -> None:
    evidence = new_evidence("entities")
    if title_suffix and title_suffix_absent:
        raise SystemExit("Pass only one of --title-suffix and --title-suffix-absent.")
    try:
        rows = entity_rows(blueprint)
    except ApiError as error:
        emit(
            {
                "ok": False,
                "command": "entities",
                "blueprint": blueprint,
                "status": error.status,
                "body": error.body,
            },
            evidence,
        )
    titles = [row.get("title") for row in rows if isinstance(row, dict)]
    sample = [
        {"identifier": row.get("identifier"), "title": row.get("title")}
        for row in rows[:limit]
        if isinstance(row, dict)
    ]
    ok = len(rows) > 0
    matched = None
    if title_suffix is not None:
        matched = sum(
            isinstance(title, str) and title.endswith(title_suffix) for title in titles
        )
        ok = len(rows) > 0 and matched == len(rows)
    if title_suffix_absent is not None:
        matched = sum(
            isinstance(title, str) and title.endswith(title_suffix_absent)
            for title in titles
        )
        ok = len(rows) > 0 and matched == 0
    emit(
        {
            "ok": ok,
            "command": "entities",
            "blueprint": blueprint,
            "count": len(rows),
            "matched": matched,
            "title_suffix": title_suffix,
            "title_suffix_absent": title_suffix_absent,
            "sample": sample,
        },
        evidence,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verify_fake_integration.py")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sync = sub.add_parser("sync")
    sync.add_argument("--timeout", type=int, default=SYNC_TIMEOUT_SECONDS)
    serve = sub.add_parser("serve")
    serve.add_argument("--timeout", type=int, default=SERVE_TIMEOUT_SECONDS)
    sub.add_parser("stop")
    sub.add_parser("routes")
    shapes = sub.add_parser("shapes")
    shapes.add_argument("--kind", required=True)
    shapes.add_argument("--count", type=int, default=1)
    shapes.add_argument("--file")
    shapes.add_argument("--post", action="store_true")
    entities = sub.add_parser("entities")
    entities.add_argument("--blueprint", required=True)
    entities.add_argument("--limit", type=int, default=20)
    entities.add_argument("--title-suffix")
    entities.add_argument("--title-suffix-absent")
    mapping = sub.add_parser("mapping")
    mapping_sub = mapping.add_subparsers(dest="mapping_command", required=True)
    show = mapping_sub.add_parser("show")
    show.add_argument("--kind", required=True)
    apply = mapping_sub.add_parser("apply")
    apply.add_argument("--file")
    apply.add_argument("--kind")
    apply.add_argument("--map", action="append", default=[])
    apply.add_argument("--run", action="store_true")
    apply.add_argument("--timeout", type=int, default=SYNC_TIMEOUT_SECONDS)
    restore = mapping_sub.add_parser("restore")
    restore.add_argument("--run", action="store_true")
    restore.add_argument("--timeout", type=int, default=SYNC_TIMEOUT_SECONDS)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "doctor":
        command_doctor()
    elif args.command == "sync":
        command_sync(args.timeout)
    elif args.command == "serve":
        command_serve(args.timeout)
    elif args.command == "stop":
        command_stop()
    elif args.command == "routes":
        command_routes()
    elif args.command == "shapes":
        command_shapes(args.kind, args.count, args.file, args.post)
    elif args.command == "entities":
        command_entities(
            args.blueprint,
            args.limit,
            args.title_suffix,
            args.title_suffix_absent,
        )
    elif args.command == "mapping" and args.mapping_command == "show":
        command_mapping_show(args.kind)
    elif args.command == "mapping" and args.mapping_command == "apply":
        command_mapping_apply(args.file, args.kind, args.map, args.run, args.timeout)
    elif args.command == "mapping" and args.mapping_command == "restore":
        command_mapping_restore(args.run, args.timeout)
    else:
        raise SystemExit(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
