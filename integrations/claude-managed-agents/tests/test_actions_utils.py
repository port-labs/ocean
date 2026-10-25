from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from actions.types import list_cost_to_usd
from actions.utils import (
    build_external_id,
    build_session_link,
    normalize_session_config,
)
from port_ocean.exceptions.execution_manager import ActionExecutionError


def test_build_external_id() -> None:
    assert build_external_id("s1", "evt_1") == "claude_session_s1_evt_1"


def test_build_session_link() -> None:
    assert (
        build_session_link("https://platform.claude.com", "ws_1", "s1")
        == "https://platform.claude.com/workspaces/ws_1/sessions/s1"
    )


def test_build_session_link_falls_back_without_workspace_id() -> None:
    assert (
        build_session_link("https://platform.claude.com", None, "s1")
        == "https://platform.claude.com/"
    )


def test_build_session_link_uses_configured_console_host() -> None:
    assert (
        build_session_link("https://console.example.com", "ws_1", "s1")
        == "https://console.example.com/workspaces/ws_1/sessions/s1"
    )


def test_list_cost_to_usd() -> None:
    assert list_cost_to_usd({"amount": "187", "currency": "USD"}) == 1.87
    assert list_cost_to_usd({"amount": "50", "currency": "USD"}) == 0.5
    assert list_cost_to_usd({"amount": "0", "currency": "USD"}) == 0.0
    assert list_cost_to_usd(None) is None
    assert list_cost_to_usd({"amount": "not-a-number"}) is None
    assert list_cost_to_usd({}) is None


@pytest.mark.asyncio
async def test_normalize_session_config_injects_github_pat() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"github_authorization_token": "ghp_test"}

    with patch("actions.utils.ocean", mock_ocean):
        api_config = await normalize_session_config(
            {
                "resources": [
                    {"type": "github_repository", "url": "https://github.com/org/repo"}
                ]
            }
        )

    assert api_config["resources"][0]["authorization_token"] == "ghp_test"


@pytest.mark.asyncio
async def test_normalize_session_config_requires_github_pat() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {}

    with patch("actions.utils.ocean", mock_ocean):
        with pytest.raises(ActionExecutionError, match="github_authorization_token"):
            await normalize_session_config(
                {
                    "resources": [
                        {
                            "type": "github_repository",
                            "url": "https://github.com/org/repo",
                        }
                    ]
                }
            )


@pytest.mark.asyncio
async def test_normalize_session_config_skips_repos_with_existing_token() -> None:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {}

    with patch("actions.utils.ocean", mock_ocean):
        api_config = await normalize_session_config(
            {
                "resources": [
                    {
                        "type": "github_repository",
                        "url": "https://github.com/org/repo",
                        "authorization_token": "already_set",
                    }
                ]
            }
        )

    assert api_config["resources"][0]["authorization_token"] == "already_set"
