from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, AsyncIterator, Iterator, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.config.settings import PortSettings

from anthropic.types.beta.sessions.beta_managed_agents_user_message_event import (
    BetaManagedAgentsUserMessageEvent,
)
from anthropic.types.beta.sessions.beta_managed_agents_text_block import (
    BetaManagedAgentsTextBlock,
)
from anthropic.types.beta.sessions.beta_managed_agents_user_interrupt_event import (
    BetaManagedAgentsUserInterruptEvent,
)
from actions.abstract_executor import AbstractAnthropicExecutor
from actions.archive_agent_executor import (
    AGENT_ARCHIVED_STATUS_LABEL,
    ArchiveAgentExecutor,
)
from actions.cancel_session_executor import (
    SESSION_CANCELLED_STATUS_LABEL,
    SESSION_NOT_CANCELLABLE_STATUS_LABEL,
    CancelSessionExecutor,
)
from actions.create_agent_executor import (
    AGENT_CREATED_STATUS_LABEL,
    CreateAgentExecutor,
)
from actions.create_environment_executor import (
    ENVIRONMENT_CREATED_STATUS_LABEL,
    CreateEnvironmentExecutor,
)
from actions.delete_environment_executor import (
    ENVIRONMENT_DELETED_STATUS_LABEL,
    DeleteEnvironmentExecutor,
)
from actions.exceptions import InvalidActionParametersException
from actions.trigger_agent_executor import (
    PORT_IDENTITY_ID_KEY,
    SESSION_NOT_CONTINUABLE_STATUS_LABEL,
    TriggerAgentExecutor,
)
from actions.update_agent_executor import (
    AGENT_UPDATED_STATUS_LABEL,
    UpdateAgentExecutor,
)
from actions.update_environment_executor import (
    ENVIRONMENT_UPDATED_STATUS_LABEL,
    UpdateEnvironmentExecutor,
)
from actions.types import TriggerAgentSessionOutput, list_cost_to_usd
from actions.port_mcp_utils import (
    PORT_MCP_SERVER_NAME,
    PortMcpBinding,
    attach_port_mcp_settings_to_agent_config,
    ensure_port_mcp_binding,
)
from actions.utils import (
    build_external_id,
    build_session_link,
    normalize_session_config,
)
from anthropic.types.beta.beta_managed_agents_session_usage import (
    BetaManagedAgentsSessionUsage,
)
from clients.anthropic_client import RateLimitInfo
from port_ocean.core.models import ActionRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from port_ocean.tests.helpers.aes_gcm import encrypt_aes256_gcm

T = TypeVar("T", bound=AbstractAnthropicExecutor)

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
