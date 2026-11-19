"""Shared constants for the integration-validation mock server."""

from __future__ import annotations

MOCK_SERVER_HOST = "127.0.0.1"
MOCK_SERVER_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

ADMIN_PREFIX = "/__admin"

UNMATCHED_RESPONSE_STATUS = 599
