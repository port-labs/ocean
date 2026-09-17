from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _identity_propagation_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Action unit tests run against the integration PAT client unless overridden."""
    monkeypatch.setattr(
        "azure_devops.actions.abstract_ado_executor._resolve_user_token",
        AsyncMock(return_value=None),
    )
