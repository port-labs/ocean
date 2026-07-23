from typing import Any

from port_ocean.context.ocean import ocean

WEBHOOK_PATH = "/webhook/{run_id}"
"""Templated so each `create_agent`/`trigger_agent` run gets its own callback
URL, with the Port run id embedded directly in the path - see
`core.webhook_signing`."""


def build_webhook_url(run_id: str) -> str | None:
    """Build the public URL Cursor should call back with agent status updates,
    with `run_id` embedded in the path (see `WEBHOOK_PATH` and
    `core.webhook_signing`).

    `None` when Ocean's public base URL isn't configured (`OCEAN__BASE_URL`),
    in which case callers fall back to the fire-and-forget path - a webhook
    can't be delivered to an integration with no reachable public URL.
    """
    base_url = ocean.app.base_url
    if not base_url:
        return None
    path = WEBHOOK_PATH.format(run_id=run_id)
    return f"{base_url.rstrip('/')}/integration{path}"


def build_webhook_config(url: str, secret: str | None = None) -> dict[str, str]:
    config: dict[str, str] = {"url": url}
    if secret is not None:
        config["secret"] = secret
    return config


def build_agent_link(console_host: str, agent_id: str) -> str:
    return f"{console_host.rstrip('/')}/agents/{agent_id}"


def normalize_model_for_v0(model: object) -> object:
    """Coerce Port model shorthand into the v0 API string shape."""
    if isinstance(model, str):
        return model
    if isinstance(model, dict) and "id" in model:
        return model["id"]
    return model


def normalize_model_for_v1(model: object) -> object:
    """Coerce Port model shorthand into the v1 API object shape."""
    if isinstance(model, str):
        return {"id": model}
    if isinstance(model, dict):
        return dict(model)
    return model


def build_v0_launch_body(
    *,
    prompt: str | None,
    repository: str | None,
    ref: str | None,
    pr_url: str | None,
    model: object | None,
    auto_create_pr: bool | None,
    webhook: dict[str, Any] | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build the v0 create body, then shallow-merge `config` at the top level.

    Mapped fields (`source`, top-level `model`, `target.autoCreatePr`) are set
    first. `config` then overrides matching top-level keys. Nested objects and
    arrays in `config` replace the whole value (not deep-merged), so use
    `config.target` for v0 target options.

    When `webhook` is provided (integration-owned completion tracking), it is
    applied after the `config` merge so it always wins.
    """
    body: dict[str, Any] = {}
    if prompt is not None:
        body["prompt"] = {"text": prompt}
    body["source"] = {
        k: v
        for k, v in {
            "repository": repository,
            "ref": ref,
            "prUrl": pr_url,
        }.items()
        if v is not None
    }
    if model is not None:
        body["model"] = model

    if auto_create_pr is not None:
        body["target"] = {"autoCreatePr": auto_create_pr}

    body.update(config)
    if "model" in body:
        body["model"] = normalize_model_for_v0(body["model"])

    if webhook is not None:
        body["webhook"] = webhook

    return body


def build_v1_create_body(
    *,
    prompt: str | None,
    repository: str | None,
    ref: str | None,
    pr_url: str | None,
    model: object | None,
    auto_create_pr: bool | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build the v1 create body, then shallow-merge `config` at the top level.

    Nested objects and arrays in `config` replace the whole value; they are not
    deep-merged.
    """
    body: dict[str, Any] = {}
    if prompt is not None:
        body["prompt"] = {"text": prompt}
    if repository is not None:
        repo: dict[str, Any] = {"url": repository}
        if pr_url is not None:
            repo["prUrl"] = pr_url
        elif ref is not None:
            repo["startingRef"] = ref
        body["repos"] = [repo]
    if model is not None:
        body["model"] = model
    if auto_create_pr is not None:
        body["autoCreatePR"] = auto_create_pr
    body.update(config)
    if "model" in body:
        body["model"] = normalize_model_for_v1(body["model"])
    return body


def build_v1_run_body(*, prompt: str | None, config: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge `config` onto the follow-up body. Nested objects/arrays in
    `config` replace the whole value; they are not deep-merged."""
    body: dict[str, Any] = {}
    if prompt is not None:
        body["prompt"] = {"text": prompt}
    body.update(config)
    return body
