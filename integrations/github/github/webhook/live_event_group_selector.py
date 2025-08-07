from typing import Any, Callable, Dict
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

Json = Dict[str, Any]

GITHUB_EVENT_TYPE_HEADER = 'x-github-event'

def _pull_request(e: Json) -> str:
    return e["pull_request"]["number"]


def _issue(e: Json) -> str:
    return e["issue"]["number"]


def _push(e: Json) -> str:
    return e["after"]


def _release(e: Json) -> str:
    return e["release"]["id"]


def _status(e: Json) -> str:
    return e["sha"]


def _wf_run(e: Json) -> str:
    return e["workflow_run"]["id"]


GITHUB_RESOURCE_ID: dict[str, Callable[[Json], str]] = {
    "pull_request": _pull_request,
    "pull_request_review_comment": _pull_request,
    "pull_request_review": _pull_request,
    "issues": _issue,
    "issue_comment": _issue,
    "push": _push,
    "release": _release,
    "status": _status,
    "workflow_run": _wf_run,
}


def get_primary_id(event: WebhookEvent) -> str | None:
    """
    Return the most relevant entity‑ID for a GitHub webhook / Events API object.
    """
    event_type = (
        event.headers.get(GITHUB_EVENT_TYPE_HEADER)
        or event.payload.get("type")
        or event.payload.get("event")
    )
    if event_type in GITHUB_RESOURCE_ID:
        try:
            event_id = str(GITHUB_RESOURCE_ID[event_type](event.payload))
            return f"{event_type}-{event_id}"
        except (KeyError, TypeError):
            pass

    stack = [event]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                if k in {"number", "id", "sha"} and isinstance(v, (int, str)):
                    return f"{event_type}-{v}"
                stack.append(v)
        elif isinstance(node, list):
            stack.extend(node)
    return None
