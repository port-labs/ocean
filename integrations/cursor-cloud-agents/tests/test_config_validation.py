import pytest
from unittest.mock import MagicMock

from actions.create_agent.context import CreateAgentContext
from actions.exceptions import InvalidActionParametersException
from actions.request_bodies import (
    parse_v0_create_body,
    parse_v1_create_body,
    parse_v1_run_body,
)
from actions.utils import build_v0_launch_body, build_v1_create_body, build_v1_run_body


def _context_from_props(**props: object) -> CreateAgentContext:
    run = MagicMock()
    run.execution_properties = props
    return CreateAgentContext.from_run(run)


def test_parse_api_version_defaults_to_v1() -> None:
    ctx = _context_from_props(prompt="go", repository="https://github.com/org/repo")
    assert ctx.api_version == "v1"


def test_parse_api_version_normalizes_case() -> None:
    ctx = _context_from_props(
        prompt="go",
        repository="https://github.com/org/repo",
        apiVersion="V0",
    )
    assert ctx.api_version == "v0"
    ctx = _context_from_props(
        prompt="go",
        repository="https://github.com/org/repo",
        apiVersion=" V1 ",
    )
    assert ctx.api_version == "v1"


def test_parse_api_version_rejects_invalid() -> None:
    with pytest.raises(InvalidActionParametersException, match="apiVersion must be"):
        _context_from_props(
            prompt="go",
            repository="https://github.com/org/repo",
            apiVersion="v2",
        )


def test_validate_report_completion_policy_rejects_v1() -> None:
    with pytest.raises(
        InvalidActionParametersException,
        match="only supported on create_agent with apiVersion v0",
    ):
        _context_from_props(
            prompt="go",
            repository="https://github.com/org/repo",
            apiVersion="v1",
            reportCompletion=True,
        )


def test_parse_v0_create_body_rejects_webhook_with_report_completion() -> None:
    body = build_v0_launch_body(
        prompt="go",
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        webhook=None,
        config={
            "webhook": {
                "url": "https://example.com/hook",
                "secret": "s" * 32,
            }
        },
    )
    with pytest.raises(
        InvalidActionParametersException,
        match="config.webhook cannot be set when reportCompletion is true",
    ):
        parse_v0_create_body(body, report_completion=True)


def test_parse_v0_create_body_allows_webhook_without_report_completion() -> None:
    body = build_v0_launch_body(
        prompt="go",
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        webhook=None,
        config={
            "webhook": {
                "url": "https://example.com/hook",
                "secret": "s" * 32,
            }
        },
    )
    parse_v0_create_body(body, report_completion=False)


def test_parse_v0_create_body_allows_v1_keys_in_merged_body() -> None:
    body = build_v0_launch_body(
        prompt="go",
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        webhook=None,
        config={"mcpServers": [], "env": {"type": "cloud", "name": "my-env"}},
    )
    parse_v0_create_body(body, report_completion=False)


def test_parse_v0_create_body_requires_prompt_text() -> None:
    with pytest.raises(InvalidActionParametersException, match="prompt.text"):
        parse_v0_create_body({"prompt": {}}, report_completion=False)


def test_parse_v1_create_body_requires_workspace() -> None:
    body = build_v1_create_body(
        prompt="go",
        repository=None,
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={},
    )
    with pytest.raises(
        InvalidActionParametersException,
        match="requires a workspace",
    ):
        parse_v1_create_body(body)


def test_parse_v1_create_body_rejects_empty_repos() -> None:
    body = build_v1_create_body(
        prompt="go",
        repository=None,
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={"repos": []},
    )
    with pytest.raises(
        InvalidActionParametersException,
        match="requires a workspace",
    ):
        parse_v1_create_body(body)


def test_parse_v1_create_body_allows_repository() -> None:
    body = build_v1_create_body(
        prompt="go",
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={},
    )
    parse_v1_create_body(body)


def test_parse_v1_create_body_allows_config_env() -> None:
    body = build_v1_create_body(
        prompt="go",
        repository=None,
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={"env": {"type": "cloud", "name": "my-env"}},
    )
    parse_v1_create_body(body)


def test_parse_v1_create_body_rejects_pr_url_only_in_merged_body() -> None:
    body = build_v1_create_body(
        prompt="go",
        repository=None,
        ref=None,
        pr_url="https://github.com/org/repo/pull/1",
        model=None,
        auto_create_pr=None,
        config={},
    )
    with pytest.raises(
        InvalidActionParametersException,
        match="requires a workspace",
    ):
        parse_v1_create_body(body)


def test_parse_v1_create_body_allows_unknown_keys() -> None:
    body = build_v1_create_body(
        prompt="go",
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={"futureCursorField": "value"},
    )
    parse_v1_create_body(body)


def test_parse_v1_create_body_requires_prompt() -> None:
    body = build_v1_create_body(
        prompt=None,
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={},
    )
    with pytest.raises(InvalidActionParametersException, match="prompt"):
        parse_v1_create_body(body)


def test_parse_v1_run_body_requires_prompt_text() -> None:
    with pytest.raises(InvalidActionParametersException, match="prompt.text"):
        parse_v1_run_body({"prompt": {}})


def test_parse_v1_run_body_accepts_follow_up_body() -> None:
    body = build_v1_run_body(
        prompt="follow up",
        config={"mode": "plan", "prompt": {"text": "follow up", "images": []}},
    )
    parse_v1_run_body(body)


def test_parse_v1_run_body_allows_unknown_keys() -> None:
    body = build_v1_run_body(
        prompt="follow up",
        config={"envVars": {"X": "y"}},
    )
    parse_v1_run_body(body)


def test_parse_v1_create_body_accepts_mcp_servers_array() -> None:
    body = build_v1_create_body(
        prompt="go",
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={
            "mcpServers": [
                {
                    "name": "linear",
                    "type": "http",
                    "url": "https://mcp.linear.app/sse",
                }
            ]
        },
    )
    parse_v1_create_body(body)


def test_parse_v1_create_body_rejects_mcp_servers_dict() -> None:
    body = build_v1_create_body(
        prompt="go",
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={
            "mcpServers": {
                "linear": {
                    "type": "http",
                    "url": "https://mcp.linear.app/sse",
                }
            }
        },
    )
    with pytest.raises(InvalidActionParametersException, match="mcpServers"):
        parse_v1_create_body(body)


def test_parse_v0_create_body_rejects_model_object() -> None:
    with pytest.raises(InvalidActionParametersException, match="model"):
        parse_v0_create_body(
            {
                "prompt": {"text": "go"},
                "model": {"id": "composer-2.5"},
            },
            report_completion=False,
        )


def test_parse_v1_create_body_rejects_non_string_env_vars() -> None:
    body = build_v1_create_body(
        prompt="go",
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={"envVars": {"PORT": 8080}},
    )
    with pytest.raises(InvalidActionParametersException, match="envVars"):
        parse_v1_create_body(body)
