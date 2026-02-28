"""Discovery module — boots an integration, runs a resync with intercepted HTTP,
and writes a structured JSON report of all captured requests.

Usage (from an integration directory):
    python -m port_ocean.tests.integration.discover
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from port_ocean.tests.integration.harness import IntegrationTestHarness
from port_ocean.tests.integration.transport import InterceptTransport


# -- Config generation helpers ------------------------------------------------


def _generate_dummy_value(config_entry: dict[str, Any]) -> Any:
    """Generate a placeholder value from a spec.yaml configuration entry."""
    if "default" in config_entry:
        return config_entry["default"]

    type_name = config_entry.get("type", "string")
    type_map: dict[str, Any] = {
        "string": "placeholder",
        "integer": 0,
        "number": 0,
        "url": "https://placeholder.example.com",
        "boolean": False,
        "array": [],
        "object": {},
    }
    return type_map.get(type_name, "placeholder")


def _build_integration_config(
    spec: dict[str, Any], integration_type: str
) -> dict[str, Any]:
    """Build a dummy integration config block from spec.yaml configurations."""
    config_values: dict[str, Any] = {}
    for entry in spec.get("configurations", []):
        name = entry.get("name")
        if name:
            config_values[name] = _generate_dummy_value(entry)

    return {
        "integration": {
            "identifier": f"test-{integration_type}",
            "type": integration_type,
            "config": config_values,
        }
    }


# -- File loaders -------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _load_mapping_config(integration_path: Path) -> dict[str, Any]:
    """Load the default mapping config from .port/resources/."""
    for name in ("port-app-config.yml", "port-app-config.yaml"):
        p = integration_path / ".port" / "resources" / name
        if p.exists():
            return _load_yaml(p)
    return {}


def _load_blueprints(integration_path: Path) -> list[dict[str, Any]]:
    """Load blueprint definitions from .port/resources/blueprints.json."""
    p = integration_path / ".port" / "resources" / "blueprints.json"
    if p.exists():
        return _load_json(p)  # type: ignore[no-any-return]
    return []


# -- Main discovery logic -----------------------------------------------------


async def run_discovery(integration_path: Path) -> dict[str, Any]:
    """Run a discovery resync and return the structured report."""
    spec_path = integration_path / ".port" / "spec.yaml"
    if not spec_path.exists():
        raise FileNotFoundError(f"No spec.yaml found at {spec_path}")

    spec = _load_yaml(spec_path)
    integration_type = spec.get("type") or integration_path.name

    # Load resources
    mapping_config = _load_mapping_config(integration_path)
    blueprints = _load_blueprints(integration_path)

    # Build dummy config
    integration_config = _build_integration_config(spec, integration_type)

    # Build blueprints dict for the port mock
    blueprints_dict: dict[str, dict[str, Any]] = {}
    for bp in blueprints:
        bp_id = bp.get("identifier", "")
        if bp_id:
            blueprints_dict[bp_id] = bp

    # Create harness with non-strict transport (captures all requests)
    transport = InterceptTransport(strict=False)
    harness = IntegrationTestHarness(
        integration_path=str(integration_path),
        port_mapping_config=mapping_config,
        third_party_transport=transport,
        port_blueprints=blueprints_dict,
        config_overrides=integration_config,
    )

    logger.info(f"Starting discovery for {integration_type}...")

    try:
        await harness.start()
        await harness.trigger_resync()
    except Exception as e:
        logger.warning(f"Discovery resync error (expected with dummy config): {e}")

    # Collect requests before shutdown (transports are still alive)
    third_party_requests = [entry.to_dict() for entry in transport.calls]
    port_requests = [entry.to_dict() for entry in harness.port_mock.transport.calls]

    await harness.shutdown()

    report: dict[str, Any] = {
        "metadata": {
            "integration_type": integration_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "integration_config": integration_config,
        "mapping_config": mapping_config,
        "blueprints": blueprints,
        "third_party_requests": third_party_requests,
        "port_requests": port_requests,
    }

    return report


def main() -> None:
    integration_path = Path.cwd()

    # Verify we're in an integration directory
    if not (integration_path / ".port" / "spec.yaml").exists():
        print(
            "Error: No .port/spec.yaml found. "
            "Run this command from an integration directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    report = asyncio.run(run_discovery(integration_path))

    # Write output
    output_path = integration_path / ".port" / "resources" / "discovery.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str) + "\n")

    n_third = len(report["third_party_requests"])
    n_port = len(report["port_requests"])
    print(f"Discovery complete: {n_third} third-party requests, {n_port} port requests")
    print(f"Report written to {output_path}")


if __name__ == "__main__":
    main()
