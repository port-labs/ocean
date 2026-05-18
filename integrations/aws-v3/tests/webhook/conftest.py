"""Webhook tests: default stub for derived account allowlist (post-auth)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

_DEFAULT_FIXTURE_ACCOUNT = "123456789012"


@pytest.fixture(autouse=True)
def _discover_valid_accounts_default() -> object:
    """`handle_event` enforces derived accounts when `allowed_account_ids` is unset.

    Unit tests call handlers directly without full integration config; stub discovery
    so they do not hit the real AWS strategy (STS/network).
    """
    with patch(
        "aws.auth.session_factory.discover_valid_account_ids",
        new=AsyncMock(return_value={_DEFAULT_FIXTURE_ACCOUNT}),
    ):
        yield
