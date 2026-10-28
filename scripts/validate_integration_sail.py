#!/usr/bin/env python3
"""PoC: sail an integration once against a local stub and assert Port entities."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

import httpx
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        val = raw.strip().strip('"').strip("'")
        values[key.strip()] = val
    return values


def _port_creds(env: dict[str, str]) -> tuple[str, str, str]:
    # B2: never take credentials as CLI args — only from env / .env
    client_id = (
        env.get("PORT_CLIENT_ID")
        or env.get("OCEAN__PORT__CLIENT_ID")
        or os.environ.get("PORT_CLIENT_ID")
        or os.environ.get("OCEAN__PORT__CLIENT_ID")
    )
    client_secret = (
        env.get("PORT_CLIENT_SECRET")
        or env.get("OCEAN__PORT__CLIENT_SECRET")
        or os.environ.get("PORT_CLIENT_SECRET")
        or os.environ.get("OCEAN__PORT__CLIENT_SECRET")
    )
    base_url = (
        env.get("PORT_BASE_URL")
        or env.get("OCEAN__PORT__BASE_URL")
        or os.environ.get("PORT_BASE_URL")
        or os.environ.get("OCEAN__PORT__BASE_URL")
        or "https://api.getport.io"
    ).rstrip("/")
    if not client_id or not client_secret:
        raise SystemExit(
            "missing Port credentials: PORT_CLIENT_ID and PORT_CLIENT_SECRET "
            "(or OCEAN__PORT__CLIENT_ID and OCEAN__PORT__CLIENT_SECRET) "
            "are not set. Validation did not run."
        )
    return client_id, client_secret, base_url


class PortApi:
    def __init__(self, client_id: str, client_secret: str, base_url: str) -> None:
        self.api_url = f"{base_url}/v1"
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self.http = httpx.Client(timeout=60.0)

    def _auth_headers(self) -> dict[str, str]:
        if not self._token:
            r = self.http.post(
                f"{self.api_url}/auth/access_token",
                json={"clientId": self.client_id, "clientSecret": self.client_secret},
            )
            r.raise_for_status()
            data = r.json()
            self._token = f"{data.get('tokenType', 'Bearer')} {data['accessToken']}"
        return {"Authorization": self._token}

    def get_blueprint(self, identifier: str) -> dict[str, Any] | None:
        r = self.http.get(
            f"{self.api_url}/blueprints/{identifier}",
            headers=self._auth_headers(),
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json().get("blueprint")

    def create_blueprint(self, definition: dict[str, Any]) -> dict[str, Any]:
        r = self.http.post(
            f"{self.api_url}/blueprints",
            headers=self._auth_headers(),
            json=definition,
        )
        r.raise_for_status()
        return r.json()["blueprint"]

    def delete_blueprint(self, identifier: str, delete_entities: bool = True) -> None:
        if delete_entities:
            r = self.http.delete(
                f"{self.api_url}/blueprints/{identifier}/all-entities",
                headers=self._auth_headers(),
                params={"delete_blueprint": "true"},
            )
        else:
            r = self.http.delete(
                f"{self.api_url}/blueprints/{identifier}",
                headers=self._auth_headers(),
            )
        # best-effort cleanup
        if r.status_code not in (200, 202, 404):
            print(
                f"warn: delete blueprint {identifier}: {r.status_code} {r.text[:200]}"
            )

    def delete_integration(self, identifier: str) -> None:
        r = self.http.delete(
            f"{self.api_url}/integration/{identifier}",
            headers=self._auth_headers(),
        )
        if r.status_code not in (200, 204, 404):
            print(
                f"warn: delete integration {identifier}: {r.status_code} {r.text[:200]}"
            )

    def search_entities_for_integration(
        self,
        *,
        integration_type: str,
        integration_identifier: str,
        blueprint: str,
    ) -> list[dict[str, Any]]:
        query = {
            "combinator": "and",
            "rules": [
                {"property": "$blueprint", "operator": "=", "value": blueprint},
                {
                    "property": "$datasource",
                    "operator": "contains",
                    "value": f"port-ocean/{integration_type}/",
                },
                {
                    "property": "$datasource",
                    "operator": "contains",
                    "value": f"/{integration_identifier}/",
                },
            ],
        }
        r = self.http.post(
            f"{self.api_url}/entities/search",
            headers=self._auth_headers(),
            json=query,
            params={
                "exclude_calculated_properties": "true",
                "include": [
                    "blueprint",
                    "identifier",
                    "title",
                    "properties",
                    "relations",
                ],
            },
        )
        r.raise_for_status()
        return r.json().get("entities") or []

    def delete_entity(self, blueprint: str, identifier: str) -> None:
        r = self.http.delete(
            f"{self.api_url}/blueprints/{blueprint}/entities/{identifier}",
            headers=self._auth_headers(),
        )
        if r.status_code not in (200, 204, 404):
            print(f"warn: delete entity {blueprint}/{identifier}: {r.status_code}")


def _load_expectations(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or not data.get("blueprint"):
        raise SystemExit("expectations file must be a mapping with a `blueprint` key")
    return data


def _assert_expectations(
    entities: list[dict[str, Any]], expectations: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    blueprint = expectations["blueprint"]

    if "count" in expectations:
        expected_count = int(expectations["count"])
        if len(entities) != expected_count:
            errors.append(
                f"count: expected {expected_count} entities for {blueprint}, got {len(entities)}"
            )

    if "identifier" in expectations:
        wanted = expectations["identifier"]
        ids = {e.get("identifier") for e in entities}
        if wanted not in ids:
            errors.append(f"identifier: expected entity {wanted!r}, have {sorted(ids)}")

    if "property" in expectations:
        prop = expectations["property"]
        name = prop["name"]
        value = prop["value"]
        matched = False
        for entity in entities:
            if entity.get("properties", {}).get(name) == value:
                matched = True
                break
        if not matched:
            errors.append(f"property: no entity with properties.{name} == {value!r}")

    if "absent" in expectations:
        absent_id = expectations["absent"]
        ids = {e.get("identifier") for e in entities}
        if absent_id in ids:
            errors.append(f"absent: entity {absent_id!r} should not exist")

    # optional list form
    for assertion in expectations.get("assertions") or []:
        if "count" in assertion:
            if len(entities) != int(assertion["count"]):
                errors.append(
                    f"assertions.count: expected {assertion['count']}, got {len(entities)}"
                )
        if "identifier" in assertion:
            ids = {e.get("identifier") for e in entities}
            if assertion["identifier"] not in ids:
                errors.append(
                    f"assertions.identifier missing: {assertion['identifier']!r}"
                )
        if "property" in assertion:
            name = assertion["property"]["name"]
            value = assertion["property"]["value"]
            if not any(e.get("properties", {}).get(name) == value for e in entities):
                errors.append(f"assertions.property missing: {name}={value!r}")
        if "absent" in assertion:
            ids = {e.get("identifier") for e in entities}
            if assertion["absent"] in ids:
                errors.append(f"assertions.absent present: {assertion['absent']!r}")

    return errors


def _integration_type(integration_path: Path) -> str:
    # folder name is the integration type in Ocean
    return integration_path.name.lower()


def _fetch_unmatched(stub_url: str) -> Any:
    try:
        r = httpx.get(f"{stub_url.rstrip('/')}/__mock/unmatched", timeout=10.0)
        if r.is_success:
            return r.json()
        return {"error": r.text}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate an Ocean integration via stub + sail"
    )
    parser.add_argument("--integration", required=True, help="Path to integration dir")
    parser.add_argument(
        "--expectations", required=True, help="Path to expectations YAML"
    )
    parser.add_argument("--stub-url", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--host-env",
        action="append",
        default=[],
        help="Env var to set to the stub URL (repeatable), e.g. OCEAN__INTEGRATION__CONFIG__API_URL",
    )
    parser.add_argument(
        "--env-file", default=None, help="Defaults to <integration>/.env then repo .env"
    )
    parser.add_argument("--keep", action="store_true", help="Skip cleanup (debug)")
    args = parser.parse_args()

    integration_path = Path(args.integration).resolve()
    expectations_path = Path(args.expectations).resolve()
    expectations = _load_expectations(expectations_path)

    env_file_candidates = []
    if args.env_file:
        env_file_candidates.append(Path(args.env_file))
    env_file_candidates.extend([integration_path / ".env", REPO_ROOT / ".env"])
    file_env: dict[str, str] = {}
    for candidate in env_file_candidates:
        file_env = _load_dotenv(candidate)
        if file_env:
            break

    client_id, client_secret, base_url = _port_creds(file_env)
    port = PortApi(client_id, client_secret, base_url)

    integration_type = _integration_type(integration_path)
    run_id = f"poc-validate-{uuid.uuid4().hex[:10]}"
    blueprint_name = expectations["blueprint"]
    created_blueprint = False
    sail_log = ""
    passed = False
    assertion_errors: list[str] = []

    print(f"run_id={run_id}")
    print(f"integration={integration_path} type={integration_type}")
    print(f"blueprint={blueprint_name} stub={args.stub_url}")

    try:
        # B4: create blueprint only when missing
        existing = port.get_blueprint(blueprint_name)
        if existing is None:
            definition = expectations.get("blueprint_definition")
            if not definition:
                raise SystemExit(
                    f"blueprint {blueprint_name!r} missing in org; "
                    "add blueprint_definition to the expectations file"
                )
            definition = dict(definition)
            definition.setdefault("identifier", blueprint_name)
            port.create_blueprint(definition)
            created_blueprint = True
            print(f"created blueprint {blueprint_name}")
        else:
            print(f"blueprint {blueprint_name} already exists")

        # B3: sail once
        child_env = os.environ.copy()
        child_env.update(file_env)
        child_env["OCEAN__PORT__CLIENT_ID"] = client_id
        child_env["OCEAN__PORT__CLIENT_SECRET"] = client_secret
        child_env["OCEAN__PORT__BASE_URL"] = base_url
        child_env["OCEAN__INTEGRATION__IDENTIFIER"] = run_id
        child_env["OCEAN__INTEGRATION__TYPE"] = integration_type
        child_env["OCEAN__EVENT_LISTENER__TYPE"] = "ONCE"
        child_env["OCEAN__CREATE_PORT_RESOURCES_ORIGIN"] = "Ocean"
        # Always initialize from local .port/resources for this validation run.
        child_env["OCEAN__INITIALIZE_PORT_RESOURCES"] = "true"
        # Force ocean-core processing so entities are upserted in-process.
        # Sandbox orgs with DSP/lakehouse flags otherwise extract raw data only
        # or abort the resync as "stale" mid-run.
        child_env["OCEAN__PROCESSING_MODE"] = "ocean-core"
        child_env["OCEAN__LAKEHOUSE_ENABLED"] = "false"

        # `import integration` must resolve to this integration. A dev venv
        # .pth (for example aws.pth) can list another integration first.
        existing_pythonpath = child_env.get("PYTHONPATH", "")
        child_env["PYTHONPATH"] = (
            f"{integration_path}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(integration_path)
        )

        host_env_from_file = expectations.get("host_env") or []
        if isinstance(host_env_from_file, str):
            host_env_from_file = [host_env_from_file]
        host_envs = list(args.host_env) + list(host_env_from_file)
        for key in host_envs:
            if not key:
                continue
            child_env[key] = args.stub_url.rstrip("/")
            print(f"host override {key}={child_env[key]}")

        # extra env from expectations
        for key, value in (expectations.get("env") or {}).items():
            child_env[str(key)] = str(value).replace(
                "${STUB_URL}", args.stub_url.rstrip("/")
            )

        # Ephemeral listen port so concurrent / leftover sails do not collide.
        sail_port = str(18000 + (uuid.uuid4().int % 1000))

        cmd = [
            sys.executable,
            "-m",
            "port_ocean.cli.cli",
            "sail",
            str(integration_path),
            "--once",
            "--port",
            sail_port,
        ]

        print(f"running: {' '.join(cmd)}")
        proc = subprocess.run(
            cmd,
            cwd=str(integration_path),
            env=child_env,
            capture_output=True,
            text=True,
        )
        sail_log = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            assertion_errors.append(f"ocean sail exited {proc.returncode}")

        # B5: assert
        entities = port.search_entities_for_integration(
            integration_type=integration_type,
            integration_identifier=run_id,
            blueprint=blueprint_name,
        )
        print(f"found {len(entities)} entities for datasource of {run_id}")
        assertion_errors.extend(_assert_expectations(entities, expectations))
        passed = not assertion_errors
    except Exception:  # noqa: BLE001
        assertion_errors.append(traceback.format_exc())
        passed = False
    finally:
        unmatched = _fetch_unmatched(args.stub_url)
        # B6 cleanup
        if not args.keep:
            try:
                entities = port.search_entities_for_integration(
                    integration_type=integration_type,
                    integration_identifier=run_id,
                    blueprint=blueprint_name,
                )
                for entity in entities:
                    port.delete_entity(blueprint_name, entity["identifier"])
            except Exception as exc:  # noqa: BLE001
                print(f"warn: entity cleanup failed: {exc}")
            try:
                port.delete_integration(run_id)
            except Exception as exc:  # noqa: BLE001
                print(f"warn: integration cleanup failed: {exc}")
            if created_blueprint:
                try:
                    port.delete_blueprint(blueprint_name, delete_entities=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"warn: blueprint cleanup failed: {exc}")

        # B7 result
        print("\n======== RESULT ========")
        print("PASS" if passed else "FAIL")
        if assertion_errors:
            print("errors:")
            for err in assertion_errors:
                print(f"  - {err}")
        print("\n-------- sail log --------")
        print(sail_log[-20000:] if sail_log else "(empty)")
        print("\n-------- unmatched stub calls --------")
        print(json.dumps(unmatched, indent=2)[:20000])

    return 0 if passed else 1


if __name__ == "__main__":
    # allow `python scripts/...` from repo root to import tools if needed
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    raise SystemExit(main())
