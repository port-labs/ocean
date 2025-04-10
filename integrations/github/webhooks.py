from typing import Any
from port_ocean.context.ocean import ocean

from utils import PortGithubResources


class GithubIssueWebhookHandler:
    async def handle_event(self, event: dict[str, Any]) -> None:
        match event.get("action"):
            case "created":
                await ocean.register_raw(PortGithubResources.ISSUE, [event["issue"]])
            case "deleted":
                await ocean.unregister_raw(PortGithubResources.ISSUE, [event["issue"]])
            case "closed":
                await ocean.register_raw(PortGithubResources.ISSUE, [event["issue"]])


class GithubPRWebhookHandler:
    async def handle_event(self, event: dict[str, Any]) -> None:
        match event.get("action"):
            case "opened":
                await ocean.register_raw(
                    PortGithubResources.PR, [event["pull_request"]]
                )
            case "closed":
                await ocean.register_raw(
                    PortGithubResources.PR, [event["pull_request"]]
                )
