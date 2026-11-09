from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, AsyncIterator, Iterator
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest
from anthropic import APIStatusError

from claude_managed_agents.actions.exceptions import InvalidActionParametersException
from claude_managed_agents.actions.trigger_agent_executor import (
    PORT_IDENTITY_ID_KEY,
    PortMcpWorkflowContext,
    SESSION_NOT_CONTINUABLE_STATUS_LABEL,
    TriggerAgentExecutor,
    TriggerAgentInputs,
    port_mcp_workflow_context,
)
from claude_managed_agents.actions.prompt_images import PromptImages
from claude_managed_agents.actions.types import TriggerAgentSessionOutput
from claude_managed_agents.actions.port_mcp_utils import (
    PORT_MCP_SERVER_NAME,
    PortMcpBinding,
)
from anthropic.types.beta.beta_managed_agents_session_usage import (
    BetaManagedAgentsSessionUsage,
)
from port_ocean.core.models import WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError


from tests.action_test_helpers import (
    build_executor,
    image_block,
    build_mock_ocean,
    empty_session_events,
    mock_ocean_with_client_secret,
    mock_event_context,
    port_mcp_agent,
    sdk_agent,
    sdk_session,
    user_message_event,
    workflow_run_with_port_mcp,
)


def test_trigger_agent_session_output_from_session() -> None:
    session = sdk_session(
        session_id="s1",
        usage=BetaManagedAgentsSessionUsage.model_validate(
            {
                "input_tokens": 5000,
                "output_tokens": 3200,
                "list_cost": {"amount": "187", "currency": "USD"},
            }
        ),
    )
    assert TriggerAgentSessionOutput.from_session(
        url="https://platform.claude.com/workspaces/ws_1/sessions/s1",
        session=session,
        session_id="s1",
        user_message_event_id="msg_1",
    ).model_dump() == {
        "sessionId": "s1",
        "userMessageEventId": "msg_1",
        "url": "https://platform.claude.com/workspaces/ws_1/sessions/s1",
        "inputTokens": 5000,
        "outputTokens": 3200,
        "costUsd": 1.87,
    }


def test_trigger_agent_session_output_relative_to_baseline() -> None:
    session = sdk_session(
        session_id="s1",
        usage=BetaManagedAgentsSessionUsage.model_validate(
            {
                "input_tokens": 5000,
                "output_tokens": 3200,
                "list_cost": {"amount": "187", "currency": "USD"},
            }
        ),
    )
    baseline = BetaManagedAgentsSessionUsage.model_validate(
        {
            "input_tokens": 2000,
            "output_tokens": 1000,
            "list_cost": {"amount": "50", "currency": "USD"},
        }
    )
    assert TriggerAgentSessionOutput.from_session(
        url="https://platform.claude.com/workspaces/ws_1/sessions/s1",
        session=session,
        baseline_usage=baseline,
    ).model_dump() == {
        "url": "https://platform.claude.com/workspaces/ws_1/sessions/s1",
        "inputTokens": 3000,
        "outputTokens": 2200,
        "costUsd": 1.37,
    }


def test_trigger_agent_session_output_url_only() -> None:
    assert TriggerAgentSessionOutput(
        url="https://platform.claude.com/"
    ).model_dump() == {"url": "https://platform.claude.com/"}


def test_port_mcp_workflow_context_enters_when_agent_already_has_port_family() -> None:
    from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
        BetaManagedAgentsMCPServerURLDefinition,
    )

    agent = port_mcp_agent()
    agent.mcp_servers = [
        *agent.mcp_servers,
        BetaManagedAgentsMCPServerURLDefinition(
            type="url",
            name="port-virtual-mcp-payments",
            url="https://mcp.getport.io/v1/virtual-server/payments",
        ),
    ]
    run = workflow_run_with_port_mcp()
    # Inputs ask for nothing; existing Port/virtual on the agent still remints.
    inputs = TriggerAgentInputs(
        agentId="agent_1",
        prompt="hi",
        environmentId="env_1",
        enablePortMcp=False,
        virtualMcpServerIds=[],
    )

    ctx = port_mcp_workflow_context(inputs, run, agent)

    assert ctx is not None
    assert ctx.enable_port_mcp is False
    assert ctx.virtual_mcp_server_ids == []


def test_port_mcp_workflow_context_skips_when_disabled_and_agent_has_no_port_family() -> (
    None
):
    run = workflow_run_with_port_mcp()
    inputs = TriggerAgentInputs(
        agentId="agent_1",
        prompt="hi",
        environmentId="env_1",
        enablePortMcp=False,
        virtualMcpServerIds=[],
    )

    assert port_mcp_workflow_context(inputs, run, sdk_agent()) is None


@pytest.mark.asyncio
async def test_resolve_port_mcp_binding_ensures_on_miss_remints_on_hit() -> None:
    from port_ocean.utils.ttl_cache import TTLCache

    client = MagicMock()
    executor = build_executor(TriggerAgentExecutor, client)
    executor._port_mcp_cache = TTLCache[PortMcpBinding](ttl_seconds=120, max_items=100)
    bindings = [
        PortMcpBinding(
            mcp_server_url="https://mcp.getport.io/v1",
            vault_id="vault_1",
            credential_id="cred_1",
        )
    ]
    agent = port_mcp_agent()

    run_1 = workflow_run_with_port_mcp(token="tok_1")
    run_2 = workflow_run_with_port_mcp(token="tok_2")
    with (
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.get_or_create_mcp_vault",
            AsyncMock(return_value=SimpleNamespace(id="vault_1")),
        ) as get_vault,
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.ensure_port_mcp_credential",
            AsyncMock(return_value=bindings[0]),
        ) as ensure,
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.remint_port_mcp_credential",
            AsyncMock(),
        ) as remint,
    ):
        ctx_1 = PortMcpWorkflowContext(run_1, run_1.execution_identity, None, True, [])
        ctx_2 = PortMcpWorkflowContext(run_2, run_2.execution_identity, None, True, [])
        first = await executor._ensure_port_mcp_vault_ready(ctx_1, agent)
        second = await executor._ensure_port_mcp_vault_ready(ctx_2, agent)

    assert first == second == "vault_1"
    get_vault.assert_awaited_once()
    ensure.assert_awaited_once()
    remint.assert_awaited_once()
    assert remint.await_args is not None
    assert remint.await_args.args[1] is run_2


@pytest.mark.asyncio
async def test_resolve_port_mcp_skips_vault_fetch_when_any_url_cached() -> None:
    from port_ocean.utils.ttl_cache import TTLCache

    from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
        BetaManagedAgentsMCPServerURLDefinition,
    )
    from claude_managed_agents.actions.port_mcp_utils import port_mcp_binding_cache_key

    port_url = "https://mcp.getport.io/v1"
    virtual_url = "https://mcp.getport.io/v1/virtual-server/payments"
    vault_name = "user@example.com"
    seeded = PortMcpBinding(
        mcp_server_url=port_url,
        vault_id="vault_1",
        credential_id="cred_port",
    )
    agent = port_mcp_agent()
    agent.mcp_servers = [
        *agent.mcp_servers,
        BetaManagedAgentsMCPServerURLDefinition(
            type="url",
            name="port-virtual-mcp-payments",
            url=virtual_url,
        ),
    ]

    client = MagicMock()
    executor = build_executor(TriggerAgentExecutor, client)
    executor._port_mcp_cache = TTLCache[PortMcpBinding](ttl_seconds=120, max_items=100)
    executor._port_mcp_cache.set(
        port_mcp_binding_cache_key(vault_name, port_url), seeded
    )

    new_binding = PortMcpBinding(
        mcp_server_url=virtual_url,
        vault_id="vault_1",
        credential_id="cred_virtual",
    )
    run = workflow_run_with_port_mcp()
    with (
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.get_or_create_mcp_vault",
            AsyncMock(),
        ) as get_vault,
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.ensure_port_mcp_credential",
            AsyncMock(return_value=new_binding),
        ) as ensure,
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.remint_port_mcp_credential",
            AsyncMock(),
        ) as remint,
    ):
        ctx = PortMcpWorkflowContext(
            run,
            run.execution_identity,
            None,
            True,
            ["payments"],
        )
        vault_id = await executor._ensure_port_mcp_vault_ready(ctx, agent)

    assert vault_id == "vault_1"
    get_vault.assert_not_awaited()
    remint.assert_awaited_once()
    ensure.assert_awaited_once_with(client, run, "vault_1", virtual_url)


@pytest.mark.asyncio
async def test_ensure_port_mcp_vault_ready_remints_each_cached_url_once() -> None:
    from port_ocean.utils.ttl_cache import TTLCache

    from claude_managed_agents.actions.port_mcp_utils import port_mcp_binding_cache_key

    port_url = "https://mcp.getport.io/v1"
    run = workflow_run_with_port_mcp()
    vault_name = run.execution_identity.identifier
    binding = PortMcpBinding(
        mcp_server_url=port_url,
        vault_id="vault_1",
        credential_id="cred_1",
    )
    client = MagicMock()
    executor = build_executor(TriggerAgentExecutor, client)
    executor._port_mcp_cache = TTLCache[PortMcpBinding](ttl_seconds=120, max_items=100)
    executor._port_mcp_cache.set(
        port_mcp_binding_cache_key(vault_name, port_url), binding
    )

    with patch(
        "claude_managed_agents.actions.trigger_agent_executor.remint_port_mcp_credential",
        AsyncMock(),
    ) as remint:
        vault_id = await executor._ensure_port_mcp_vault_ready(
            PortMcpWorkflowContext(run, run.execution_identity, None, True, []),
            port_mcp_agent(),
        )

    assert vault_id == "vault_1"
    assert remint.await_count == 1


@pytest.mark.asyncio
async def test_trigger_agent_managed_port_mcp_attaches_vault_on_create() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=port_mcp_agent())
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = workflow_run_with_port_mcp()
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.TriggerAgentExecutor._ensure_port_mcp_vault_ready",
            AsyncMock(return_value="vault_port"),
        ) as resolve_binding,
    ):
        await executor.execute(run)

    resolve_binding.assert_awaited_once()
    client_mock.create_session.assert_awaited_once_with(
        "agent_1",
        "env_1",
        extra={
            "metadata": {PORT_IDENTITY_ID_KEY: "user@example.com"},
            "vault_ids": ["vault_port"],
        },
    )


@pytest.mark.asyncio
async def test_trigger_agent_enable_port_mcp_wires_agent_without_existing_mcp() -> None:
    from port_ocean.utils.ttl_cache import TTLCache

    agent = sdk_agent(agent_id="agent_wire_mcp", version=3)
    updated_agent = port_mcp_agent(agent_id="agent_wire_mcp", version=4)
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=agent)
    client_mock.update_agent = AsyncMock(return_value=updated_agent)
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    executor = build_executor(TriggerAgentExecutor, client_mock)
    executor._agent_cache = TTLCache(max_items=100, ttl_seconds=120)

    run = workflow_run_with_port_mcp(
        execution_properties={
            "agentId": "agent_wire_mcp",
            "environmentId": "env_1",
            "prompt": "go",
            "reportSessionStatus": True,
        }
    )
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.TriggerAgentExecutor._ensure_port_mcp_vault_ready",
            AsyncMock(return_value="vault_port"),
        ),
    ):
        await executor.execute(run)

    client_mock.update_agent.assert_awaited_once()
    update_kwargs = client_mock.update_agent.await_args.kwargs
    assert update_kwargs["version"] == 3
    assert PORT_MCP_SERVER_NAME in str(update_kwargs["payload"])


@pytest.mark.asyncio
async def test_trigger_agent_enable_port_mcp_false_skips_when_agent_has_no_port_family() -> (
    None
):
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    client_mock.update_agent = AsyncMock()
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = workflow_run_with_port_mcp(
        execution_properties={
            "agentId": "agent_1",
            "environmentId": "env_1",
            "prompt": "go",
            "enablePortMcp": False,
            "reportSessionStatus": True,
        }
    )
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.TriggerAgentExecutor._ensure_port_mcp_vault_ready",
            AsyncMock(),
        ) as resolve_binding,
    ):
        await executor.execute(run)

    client_mock.update_agent.assert_not_called()
    resolve_binding.assert_not_awaited()
    extra = client_mock.create_session.await_args.kwargs.get("extra") or {}
    assert "vault_ids" not in extra


@pytest.mark.asyncio
async def test_trigger_agent_enable_port_mcp_false_still_remints_existing_port_family() -> (
    None
):
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=port_mcp_agent())
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    client_mock.update_agent = AsyncMock()
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = workflow_run_with_port_mcp(
        execution_properties={
            "agentId": "agent_1",
            "environmentId": "env_1",
            "prompt": "go",
            "enablePortMcp": False,
            "reportSessionStatus": True,
        }
    )
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.TriggerAgentExecutor._ensure_port_mcp_vault_ready",
            AsyncMock(return_value="vault_port"),
        ) as resolve_binding,
    ):
        await executor.execute(run)

    client_mock.update_agent.assert_not_called()
    resolve_binding.assert_awaited_once()
    extra = client_mock.create_session.await_args.kwargs.get("extra") or {}
    assert extra.get("vault_ids") == ["vault_port"]


@pytest.mark.asyncio
async def test_trigger_agent_managed_port_mcp_skips_vault_without_execution_identity() -> (
    None
):
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.update_agent = AsyncMock()
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.port_access_token = None
    run.execution_identity = None
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "reportSessionStatus": True,
    }
    run.output = {}

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()
    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.TriggerAgentExecutor._ensure_port_mcp_vault_ready",
            AsyncMock(),
        ) as resolve_binding,
    ):
        await executor.execute(run)

    resolve_binding.assert_not_awaited()
    client_mock.update_agent.assert_not_called()
    client_mock.create_session.assert_awaited_once()
    extra = client_mock.create_session.await_args.kwargs.get("extra") or {}
    assert "vault_ids" not in extra


@pytest.mark.asyncio
async def test_trigger_agent_managed_port_mcp_fails_without_token() -> None:
    existing_vault = SimpleNamespace(id="vault_1", display_name="user@example.com")
    vault_pages: Iterator[list[Any]] = iter([[existing_vault], []])

    async def _paginate(*_args: Any, **_kwargs: Any) -> AsyncIterator[list[Any]]:
        yield next(vault_pages)

    client_mock = MagicMock()
    client_mock.paginate = _paginate
    client_mock.get_agent = AsyncMock(return_value=port_mcp_agent())
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock(spec=WorkflowNodeRun)
    run.id = "run_1"
    run.action_type = "trigger_agent"
    run.port_access_token = None
    run.execution_identity = SimpleNamespace(
        type="actor", identifier="user@example.com"
    )
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
    }

    with (
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.ocean",
            build_mock_ocean(),
        ),
        patch(
            "claude_managed_agents.actions.port_mcp_utils.get_run_access_token",
            side_effect=ActionExecutionError(
                "portAccessToken is required when executionIdentity is set"
            ),
        ),
        pytest.raises(ActionExecutionError, match="portAccessToken"),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_agent_managed_port_mcp_continue_remints_and_checks_identity() -> (
    None
):
    session = sdk_session(
        metadata={PORT_IDENTITY_ID_KEY: "user@example.com"},
        vault_ids=["vault_port"],
    )
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=port_mcp_agent())
    client_mock.get_session = AsyncMock(return_value=session)
    client_mock.get_session_events = empty_session_events
    client_mock.send_user_message = AsyncMock(return_value=user_message_event("msg_2"))
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = workflow_run_with_port_mcp(
        execution_properties={
            "agentId": "agent_1",
            "sessionId": "sess_1",
            "prompt": "follow up",
            "reportSessionStatus": True,
        }
    )
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.TriggerAgentExecutor._ensure_port_mcp_vault_ready",
            AsyncMock(return_value="vault_port"),
        ) as resolve_binding,
    ):
        await executor.execute(run)

    resolve_binding.assert_awaited_once()
    client_mock.create_session.assert_not_called()
    client_mock.send_user_message.assert_awaited_once_with("sess_1", "follow up", [])


async def execute_continuing(
    prompt: str, images: PromptImages, send_effect: Any = None
) -> tuple[Any, Any]:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=port_mcp_agent())
    client_mock.get_session = AsyncMock(return_value=sdk_session())
    client_mock.get_session_events = empty_session_events
    client_mock.send_user_message = AsyncMock(
        return_value=user_message_event("msg_2"), side_effect=send_effect
    )
    from port_ocean.utils.ttl_cache import TTLCache

    from anthropic.types.beta import BetaManagedAgentsAgent

    executor = build_executor(TriggerAgentExecutor, client_mock)
    executor._agent_cache = TTLCache[BetaManagedAgentsAgent](
        ttl_seconds=120, max_items=100
    )
    run = workflow_run_with_port_mcp(
        execution_properties={
            "agentId": "agent_1",
            "sessionId": "sess_1",
            "prompt": prompt,
            "reportSessionStatus": True,
        }
    )
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.load_prompt_images",
            AsyncMock(return_value=images),
        ),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.TriggerAgentExecutor._ensure_port_mcp_vault_ready",
            AsyncMock(return_value="vault_port"),
        ),
    ):
        await executor.execute(run)
    return client_mock, mock_ocean


IMAGE_BLOCKS: list[Any] = [{"type": "text", "text": "Image 1:"}, image_block()]


@pytest.mark.asyncio
async def test_trigger_agent_sends_the_relabeled_prompt_and_the_images_after_it() -> (
    None
):
    client_mock, _ = await execute_continuing(
        "see ![x](https://assets.io/organizations/o/markdown_image/a.png)",
        PromptImages("see [Image 1: x]", blocks=IMAGE_BLOCKS),
    )

    client_mock.send_user_message.assert_awaited_once_with(
        "sess_1", "see [Image 1: x]", IMAGE_BLOCKS
    )


GONE = "https://assets.io/organizations/o/markdown_image/gone.png"
KEPT = "https://assets.io/organizations/o/markdown_image/a.png"


def rejected(status: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/sessions")
    return APIStatusError(
        "image rejected", response=httpx.Response(status, request=request), body=None
    )


def warnings(mock_ocean: Any) -> list[str]:
    return [
        call.args[1]
        for call in mock_ocean.port_client.post_run_log.await_args_list
        if call.kwargs.get("level") == "WARNING"
    ]


@pytest.mark.asyncio
async def test_trigger_agent_logs_the_images_it_could_not_attach_and_still_runs() -> (
    None
):
    client_mock, mock_ocean = await execute_continuing(
        f"see {GONE}",
        PromptImages("see [Image 1 - not attached]", failed=[GONE]),
    )

    client_mock.send_user_message.assert_awaited_once_with(
        "sess_1", "see [Image 1 - not attached]", []
    )
    [warning] = warnings(mock_ocean)
    assert GONE in warning


@pytest.mark.asyncio
async def test_trigger_agent_lists_a_limited_number_of_images_it_could_not_attach() -> (
    None
):
    gone = [
        f"https://assets.io/organizations/o/markdown_image/{i}.png" for i in range(30)
    ]

    _, mock_ocean = await execute_continuing("see", PromptImages("see", failed=gone))

    [warning] = warnings(mock_ocean)
    assert gone[9] in warning and gone[10] not in warning and warning.endswith("...")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 413])
async def test_trigger_agent_sends_the_prompt_without_the_images_claude_rejects(
    status: int,
) -> None:
    client_mock, mock_ocean = await execute_continuing(
        f"see ![x]({KEPT})",
        PromptImages("see [Image 1: x]", blocks=IMAGE_BLOCKS),
        send_effect=[rejected(status), user_message_event("msg_2")],
    )

    assert client_mock.send_user_message.await_args_list == [
        call("sess_1", "see [Image 1: x]", IMAGE_BLOCKS),
        call("sess_1", "see [Image 1: x - not attached]"),
    ]
    [warning] = warnings(mock_ocean)
    assert str(status) in warning


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "images, status",
    [
        (PromptImages("see [Image 1: x]", blocks=IMAGE_BLOCKS), 500),
        (PromptImages("no images"), 400),
    ],
)
async def test_trigger_agent_does_not_hide_other_send_failures(
    images: PromptImages, status: int
) -> None:
    with pytest.raises(APIStatusError):
        await execute_continuing("no images", images, send_effect=[rejected(status)])


@pytest.mark.asyncio
async def test_trigger_agent_managed_port_mcp_rejects_cross_identity_continue() -> None:
    session = sdk_session(
        metadata={PORT_IDENTITY_ID_KEY: "alice@example.com"},
        vault_ids=["vault_alice"],
    )
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=port_mcp_agent())
    client_mock.get_session = AsyncMock(return_value=session)
    client_mock.get_session_events = empty_session_events
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = workflow_run_with_port_mcp(
        identity=SimpleNamespace(type="actor", identifier="bob@example.com"),
        execution_properties={
            "agentId": "agent_1",
            "sessionId": "sess_1",
            "prompt": "follow up",
        },
    )

    mock_ocean = mock_ocean_with_client_secret()
    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.utils.ocean", mock_ocean),
        patch("port_ocean.core.handlers.actions.utils.ocean", mock_ocean),
        pytest.raises(ActionExecutionError, match="owned by alice@example.com"),
    ):
        await executor.execute(run)

    client_mock.send_user_message.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_agent_executor_starts_session() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "enablePortMcp": False,
        "reportSessionStatus": True,
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_awaited_once_with(
        "agent_1",
        "env_1",
        extra=None,
    )
    client_mock.send_user_message.assert_awaited_once_with("sess_1", "go", [])
    mock_ocean.register_raw.assert_awaited_once()
    mock_ocean.port_client.update_run_started.assert_awaited_once()
    call = mock_ocean.port_client.update_run_started.call_args
    assert call.args[2] == "claude_session_sess_1_msg_1"
    assert call.kwargs["extra_output"] == {
        "sessionId": "sess_1",
        "userMessageEventId": "msg_1",
        "url": call.args[1],
    }


@pytest.mark.asyncio
async def test_trigger_agent_executor_passes_config_on_new_session() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "config": {
            "title": "My session",
            "metadata": {"team": "platform"},
            "vault_ids": ["vault_1"],
            "resources": [{"type": "memory_store", "memory_store_id": "ms_1"}],
        },
        "enablePortMcp": False,
        "reportSessionStatus": True,
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.utils.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_awaited_once_with(
        "agent_1",
        "env_1",
        extra={
            "title": "My session",
            "metadata": {"team": "platform"},
            "vault_ids": ["vault_1"],
            "resources": [{"type": "memory_store", "memory_store_id": "ms_1"}],
        },
    )


@pytest.mark.asyncio
async def test_trigger_agent_executor_requires_config_object() -> None:
    client_mock = MagicMock()
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "config": "not-an-object",
    }

    with pytest.raises(InvalidActionParametersException, match="config"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_trigger_agent_executor_ignores_session_create_fields_when_continuing() -> (
    None
):
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.get_session = AsyncMock(return_value=sdk_session())
    client_mock.get_session_events = empty_session_events
    client_mock.send_user_message = AsyncMock(return_value=user_message_event("msg_2"))
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_2"
    run.execution_properties = {
        "agentId": "agent_1",
        "sessionId": "sess_1",
        "prompt": "follow up",
        "config": {"title": "Should be ignored"},
        "enablePortMcp": False,
        "reportSessionStatus": True,
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_agent_partition_key_is_none_for_new_session() -> None:
    executor = build_executor(TriggerAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "agent_1"}
    assert await executor._get_partition_key(run) is None


@pytest.mark.asyncio
async def test_trigger_agent_partition_key_is_session_id_when_continuing() -> None:
    executor = build_executor(TriggerAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "agent_1", "sessionId": "sess_1"}
    assert await executor._get_partition_key(run) == "sess_1"


@pytest.mark.asyncio
async def test_trigger_agent_continues_idle_session() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.get_session = AsyncMock(return_value=sdk_session())
    client_mock.get_session_events = empty_session_events
    client_mock.send_user_message = AsyncMock(return_value=user_message_event("msg_2"))
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_2"
    run.execution_properties = {
        "agentId": "agent_1",
        "sessionId": "sess_1",
        "prompt": "follow up",
        "enablePortMcp": False,
        "reportSessionStatus": True,
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_not_called()
    client_mock.send_user_message.assert_awaited_once_with("sess_1", "follow up", [])
    assert (
        mock_ocean.port_client.update_run_started.call_args.args[2]
        == "claude_session_sess_1_msg_2"
    )


@pytest.mark.asyncio
async def test_trigger_agent_rejects_non_idle_session() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.get_session = AsyncMock(return_value=sdk_session(status="running"))
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.execution_properties = {
        "agentId": "agent_1",
        "sessionId": "sess_1",
        "prompt": "go",
        "enablePortMcp": False,
    }

    with patch(
        "claude_managed_agents.actions.trigger_agent_executor.ocean", build_mock_ocean()
    ):
        with pytest.raises(
            ActionExecutionError, match="cannot be continued"
        ) as exc_info:
            await executor.execute(run)

    assert exc_info.value.status_label == SESSION_NOT_CONTINUABLE_STATUS_LABEL


@pytest.mark.asyncio
async def test_trigger_agent_rejects_requires_action_idle() -> None:
    from anthropic.types.beta.sessions.beta_managed_agents_session_requires_action import (
        BetaManagedAgentsSessionRequiresAction,
    )
    from anthropic.types.beta.sessions.beta_managed_agents_session_status_idle_event import (
        BetaManagedAgentsSessionStatusIdleEvent,
    )

    idle_event = BetaManagedAgentsSessionStatusIdleEvent(
        id="idle_1",
        type="session.status_idle",
        processed_at=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        stop_reason=BetaManagedAgentsSessionRequiresAction(
            type="requires_action", event_ids=["evt_1"]
        ),
    )

    async def _idle_events(
        _session_id: str, **kwargs: object
    ) -> AsyncIterator[list[object]]:
        yield [idle_event]

    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.get_session = AsyncMock(return_value=sdk_session())
    client_mock.get_session_events = _idle_events
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.execution_properties = {
        "agentId": "agent_1",
        "sessionId": "sess_1",
        "prompt": "go",
        "enablePortMcp": False,
    }

    with patch(
        "claude_managed_agents.actions.trigger_agent_executor.ocean", build_mock_ocean()
    ):
        with pytest.raises(
            ActionExecutionError, match="waiting for user action"
        ) as exc_info:
            await executor.execute(run)

    assert exc_info.value.status_label == SESSION_NOT_CONTINUABLE_STATUS_LABEL


@pytest.mark.asyncio
async def test_trigger_agent_requires_environment_for_new_session() -> None:
    executor = build_executor(TriggerAgentExecutor, MagicMock())
    run = MagicMock()
    run.execution_properties = {"agentId": "agent_1", "prompt": "go"}
    with patch(
        "claude_managed_agents.actions.trigger_agent_executor.ocean", build_mock_ocean()
    ):
        with pytest.raises(InvalidActionParametersException, match="environmentId"):
            await executor.execute(run)


@pytest.mark.asyncio
async def test_trigger_agent_executor_injects_github_pat_into_session_config() -> None:
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "config": {
            "resources": [
                {"type": "github_repository", "url": "https://github.com/org/repo"}
            ]
        },
        "enablePortMcp": False,
        "reportSessionStatus": True,
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.integration_config = {"github_authorization_token": "ghp_test"}
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.utils.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
    ):
        await executor.execute(run)

    client_mock.create_session.assert_awaited_once_with(
        "agent_1",
        "env_1",
        extra={
            "resources": [
                {
                    "type": "github_repository",
                    "url": "https://github.com/org/repo",
                    "authorization_token": "ghp_test",
                }
            ],
        },
    )


@pytest.mark.asyncio
async def test_trigger_agent_executor_completes_run_synchronously_when_report_status_false() -> (
    None
):
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "enablePortMcp": False,
        "reportSessionStatus": False,
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
    ):
        await executor.execute(run)

    mock_ocean.port_client.update_run_started.assert_awaited_once()
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is True


@pytest.mark.asyncio
async def test_trigger_agent_executor_completes_run_synchronously_by_default() -> None:
    """reportSessionStatus defaults to False: without a webhook configured on the
    integration, a run left in progress would never complete."""
    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    executor = build_executor(TriggerAgentExecutor, client_mock)

    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {
        "agentId": "agent_1",
        "environmentId": "env_1",
        "prompt": "go",
        "enablePortMcp": False,
    }

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()
    mock_ocean.port_client.report_run_completed = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
    ):
        await executor.execute(run)

    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is True


@pytest.mark.asyncio
async def test_continue_rejects_owned_session_without_execution_identity() -> None:
    session = sdk_session(metadata={PORT_IDENTITY_ID_KEY: "user@example.com"})
    client = MagicMock()
    client.get_session = AsyncMock(return_value=session)
    client.get_session_events = empty_session_events
    executor = build_executor(TriggerAgentExecutor, client)
    run = workflow_run_with_port_mcp()
    run.execution_identity = None

    with pytest.raises(ActionExecutionError, match="without an execution identity"):
        await executor._ensure_session_continuable("sess_1", run)


@pytest.mark.asyncio
async def test_continue_allows_session_without_port_owner() -> None:
    session = sdk_session(metadata={})
    client = MagicMock()
    client.get_session = AsyncMock(return_value=session)
    client.get_session_events = empty_session_events
    executor = build_executor(TriggerAgentExecutor, client)

    result = await executor._ensure_session_continuable(
        "sess_1", workflow_run_with_port_mcp()
    )
    assert result is session


@pytest.mark.asyncio
async def test_trigger_agent_git_pat_injects_mount_and_vault() -> None:
    from port_ocean.utils.ttl_cache import TTLCache
    from claude_managed_agents.actions.git_auth.types import GITHUB_MCP_SERVER_NAME

    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    client_mock.update_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(TriggerAgentExecutor, client_mock)
    executor._agent_cache = TTLCache(max_items=100, ttl_seconds=120)

    run = workflow_run_with_port_mcp(
        execution_properties={
            "agentId": "agent_1",
            "environmentId": "env_1",
            "prompt": "open a pr",
            "enablePortMcp": False,
            "gitProvider": "github",
            "gitAuthMethod": "bearerToken",
            "gitAccessToken": "ghp_test",
            "config": {
                "resources": [
                    {"type": "github_repository", "url": "https://github.com/org/repo"}
                ]
            },
            "reportSessionStatus": True,
        }
    )
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
        patch("claude_managed_agents.actions.utils.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.ensure_git_mcp_credential",
            AsyncMock(
                return_value=PortMcpBinding(
                    mcp_server_url="https://api.githubcopilot.com/mcp",
                    vault_id="vault_git",
                    credential_id="cred_git",
                )
            ),
        ) as ensure_git,
    ):
        await executor.execute(run)

    ensure_git.assert_awaited_once()
    extra = client_mock.create_session.await_args.kwargs.get("extra") or {}
    assert extra["resources"][0]["authorization_token"] == "ghp_test"
    assert "vault_git" in extra["vault_ids"]
    client_mock.update_agent.assert_awaited_once()
    assert (
        client_mock.update_agent.await_args.kwargs["payload"]["mcp_servers"][0].name
        == GITHUB_MCP_SERVER_NAME
    )


@pytest.mark.asyncio
async def test_trigger_agent_enable_git_mcp_false_skips_mcp() -> None:
    from port_ocean.utils.ttl_cache import TTLCache

    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(return_value=sdk_agent())
    client_mock.create_session = AsyncMock(return_value=sdk_session())
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    client_mock.update_agent = AsyncMock()
    executor = build_executor(TriggerAgentExecutor, client_mock)
    executor._agent_cache = TTLCache(max_items=100, ttl_seconds=120)

    run = workflow_run_with_port_mcp(
        execution_properties={
            "agentId": "agent_1",
            "environmentId": "env_1",
            "prompt": "push a branch",
            "enablePortMcp": False,
            "enableGitMcp": False,
            "gitProvider": "github",
            "gitAuthMethod": "bearerToken",
            "gitAccessToken": "ghp_test",
            "config": {
                "resources": [
                    {"type": "github_repository", "url": "https://github.com/org/repo"}
                ]
            },
            "reportSessionStatus": True,
        }
    )
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
        patch("claude_managed_agents.actions.utils.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.ensure_git_mcp_credential",
            AsyncMock(),
        ) as ensure_git,
    ):
        await executor.execute(run)

    ensure_git.assert_not_awaited()
    client_mock.update_agent.assert_not_called()
    extra = client_mock.create_session.await_args.kwargs.get("extra") or {}
    assert extra["resources"][0]["authorization_token"] == "ghp_test"
    assert "vault_ids" not in extra


@pytest.mark.asyncio
async def test_trigger_agent_continue_remints_git_mcp() -> None:
    from port_ocean.utils.ttl_cache import TTLCache
    from anthropic.types.beta.beta_managed_agents_mcp_server_url_definition import (
        BetaManagedAgentsMCPServerURLDefinition,
    )
    from claude_managed_agents.actions.git_auth.types import GITHUB_MCP_SERVER_NAME

    client_mock = MagicMock()
    client_mock.get_agent = AsyncMock(
        return_value=sdk_agent(
            mcp_servers=[
                BetaManagedAgentsMCPServerURLDefinition(
                    type="url",
                    name=GITHUB_MCP_SERVER_NAME,
                    url="https://api.githubcopilot.com/mcp",
                )
            ]
        )
    )
    client_mock.get_session = AsyncMock(return_value=sdk_session())
    client_mock.get_session_events = empty_session_events
    client_mock.send_user_message = AsyncMock(return_value=user_message_event())
    client_mock.create_session = AsyncMock()
    client_mock.update_agent = AsyncMock()
    executor = build_executor(TriggerAgentExecutor, client_mock)
    executor._agent_cache = TTLCache(max_items=100, ttl_seconds=120)

    run = workflow_run_with_port_mcp(
        execution_properties={
            "agentId": "agent_1",
            "sessionId": "sess_1",
            "prompt": "continue",
            "enablePortMcp": False,
            "gitProvider": "github",
            "gitAuthMethod": "bearerToken",
            "gitAccessToken": "ghp_new",
            "reportSessionStatus": True,
        }
    )
    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.update_run_started = AsyncMock()

    with (
        patch("claude_managed_agents.actions.trigger_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
        patch(
            "claude_managed_agents.actions.trigger_agent_executor.ensure_git_mcp_credential",
            AsyncMock(
                return_value=PortMcpBinding(
                    mcp_server_url="https://api.githubcopilot.com/mcp",
                    vault_id="vault_git",
                    credential_id="cred_git",
                )
            ),
        ) as ensure_git,
    ):
        await executor.execute(run)

    ensure_git.assert_awaited_once()
    client_mock.create_session.assert_not_called()
