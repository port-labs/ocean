"""CLI entry point for the integration-validation mock server."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import uvicorn

from tools.integration_validation.mock_server.app import create_mock_server_app
from tools.integration_validation.mock_server.constants import MOCK_SERVER_HOST


def run_mock_server(fixture_root: Path | str, port: int) -> None:
    """Run the mock server on loopback only."""
    uvicorn.run(
        create_mock_server_app(fixture_root),
        host=MOCK_SERVER_HOST,
        port=port,
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the Ocean integration-validation mock server."
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        required=True,
        help=(
            "Root for mock scenario fixtures (route YAMLs and response bodies) "
            "loaded via the admin API; typically <integration>/tests/validation/mock."
        ),
    )
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args(argv)
    run_mock_server(args.fixture_root, args.port)
