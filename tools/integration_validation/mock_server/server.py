"""FastAPI application for the integration-validation mock server."""

from __future__ import annotations

import uvicorn

from tools.integration_validation.mock_server.app import create_mock_server_app
from tools.integration_validation.mock_server.cli import main, run_mock_server
from tools.integration_validation.mock_server.constants import (
    MOCK_SERVER_HOST,
    MOCK_SERVER_METHODS,
)

__all__ = [
    "MOCK_SERVER_HOST",
    "MOCK_SERVER_METHODS",
    "create_mock_server_app",
    "main",
    "run_mock_server",
    "uvicorn",
]


if __name__ == "__main__":
    main()
