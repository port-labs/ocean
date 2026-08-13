from actions.utils import (
    build_agent_link,
    build_v0_launch_body,
    build_v1_create_body,
    build_v1_run_body,
)


def test_build_v0_launch_body_minimal() -> None:
    body = build_v0_launch_body(
        prompt="Add a README",
        repository="https://github.com/org/repo",
        ref="main",
        pr_url=None,
        model=None,
        auto_create_pr=None,
        webhook=None,
        config={},
    )

    assert body == {
        "prompt": {"text": "Add a README"},
        "source": {"repository": "https://github.com/org/repo", "ref": "main"},
    }


def test_build_v0_launch_body_full() -> None:
    body = build_v0_launch_body(
        prompt="Add a README",
        repository="https://github.com/org/repo",
        ref="main",
        pr_url=None,
        model="claude-4.5-sonnet-thinking",
        auto_create_pr=True,
        webhook={"url": "https://hook", "secret": "s" * 32},
        config={"target": {"branchName": "feature/readme"}},
    )

    assert body == {
        "prompt": {"text": "Add a README"},
        "source": {"repository": "https://github.com/org/repo", "ref": "main"},
        "model": "claude-4.5-sonnet-thinking",
        "target": {"branchName": "feature/readme"},
        "webhook": {"url": "https://hook", "secret": "s" * 32},
    }


def test_build_v0_launch_body_config_model_overrides_top_level() -> None:
    body = build_v0_launch_body(
        prompt="Add a README",
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model="ignored-model",
        auto_create_pr=None,
        webhook=None,
        config={"model": {"id": "composer-2.5"}},
    )

    assert body["model"] == "composer-2.5"


def test_build_v0_launch_body_report_completion_webhook_wins_over_config() -> None:
    body = build_v0_launch_body(
        prompt="Add a README",
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        webhook={"url": "https://owned", "secret": "owned-secret"},
        config={"webhook": {"url": "https://user", "secret": "user-secret"}},
    )

    assert body["webhook"] == {"url": "https://owned", "secret": "owned-secret"}


def test_build_v0_launch_body_uses_pr_url_instead_of_repository() -> None:
    body = build_v0_launch_body(
        prompt="Fix it",
        repository=None,
        ref=None,
        pr_url="https://github.com/org/repo/pull/1",
        model=None,
        auto_create_pr=None,
        webhook=None,
        config={},
    )

    assert body["source"] == {"prUrl": "https://github.com/org/repo/pull/1"}


def test_build_v1_create_body_with_repository_and_ref() -> None:
    body = build_v1_create_body(
        prompt="Add a README",
        repository="https://github.com/org/repo",
        ref="main",
        pr_url=None,
        model="composer-2",
        auto_create_pr=True,
        config={},
    )

    assert body == {
        "prompt": {"text": "Add a README"},
        "repos": [{"url": "https://github.com/org/repo", "startingRef": "main"}],
        "model": {"id": "composer-2"},
        "autoCreatePR": True,
    }


def test_build_v1_create_body_with_pr_url_ignores_ref() -> None:
    body = build_v1_create_body(
        prompt="Fix it",
        repository="https://github.com/org/repo",
        ref="main",
        pr_url="https://github.com/org/repo/pull/1",
        model=None,
        auto_create_pr=None,
        config={},
    )

    assert body["repos"] == [
        {
            "url": "https://github.com/org/repo",
            "prUrl": "https://github.com/org/repo/pull/1",
        }
    ]


def test_build_v1_create_body_no_repository_omits_repos() -> None:
    body = build_v1_create_body(
        prompt="Just chat",
        repository=None,
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={},
    )

    assert "repos" not in body


def test_build_v1_create_body_with_model_object() -> None:
    body = build_v1_create_body(
        prompt="Add a README",
        repository=None,
        ref=None,
        pr_url=None,
        model={
            "id": "composer-2.5",
            "params": [{"id": "fast", "value": "false"}],
        },
        auto_create_pr=None,
        config={},
    )

    assert body == {
        "prompt": {"text": "Add a README"},
        "model": {
            "id": "composer-2.5",
            "params": [{"id": "fast", "value": "false"}],
        },
    }


def test_build_v1_create_body_with_env_config() -> None:
    body = build_v1_create_body(
        prompt="Run in saved env",
        repository=None,
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={"env": {"type": "cloud", "name": "my-env"}},
    )

    assert body == {
        "prompt": {"text": "Run in saved env"},
        "env": {"type": "cloud", "name": "my-env"},
    }


def test_build_v1_create_body_config_overrides_derived_fields() -> None:
    body = build_v1_create_body(
        prompt="Add a README",
        repository="https://github.com/org/repo",
        ref="main",
        pr_url=None,
        model="composer-2",
        auto_create_pr=None,
        config={
            "model": {"id": "gpt-5.6", "params": [{"id": "fast", "value": "true"}]}
        },
    )

    assert body["model"] == {
        "id": "gpt-5.6",
        "params": [{"id": "fast", "value": "true"}],
    }


def test_build_v1_run_body() -> None:
    body = build_v1_run_body(
        prompt="Also add troubleshooting",
        config={"mode": "plan"},
    )

    assert body == {"prompt": {"text": "Also add troubleshooting"}, "mode": "plan"}


def test_build_v1_run_body_omits_prompt_when_only_in_config() -> None:
    body = build_v1_run_body(
        prompt=None,
        config={"prompt": {"text": "from config"}, "mode": "plan"},
    )

    assert body == {"prompt": {"text": "from config"}, "mode": "plan"}


def test_build_v1_create_body_omits_prompt_when_only_in_config() -> None:
    body = build_v1_create_body(
        prompt=None,
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        config={"prompt": {"text": "from config"}},
    )

    assert body == {
        "repos": [{"url": "https://github.com/org/repo"}],
        "prompt": {"text": "from config"},
    }


def test_build_v0_launch_body_omits_prompt_when_only_in_config() -> None:
    body = build_v0_launch_body(
        prompt=None,
        repository="https://github.com/org/repo",
        ref=None,
        pr_url=None,
        model=None,
        auto_create_pr=None,
        webhook=None,
        config={"prompt": {"text": "from config"}},
    )

    assert body == {
        "source": {"repository": "https://github.com/org/repo"},
        "prompt": {"text": "from config"},
    }


def test_build_agent_link_strips_trailing_slash() -> None:
    assert (
        build_agent_link("https://cursor.com/", "bc-1")
        == "https://cursor.com/agents/bc-1"
    )
