from __future__ import annotations

from port_ocean.context.ocean import ocean

from azure_integration.foundry.clients.webhook_client import has_any_signing_secret


def foundry_webhook_completion_available() -> bool:
    """True when Ocean can receive Foundry ``response.*`` webhooks."""
    if not ocean.app.base_url:
        return False
    if not ocean.app.config.event_listener.should_process_webhooks:
        return False
    return True


def invoke_agent_completion_mode(*, report_invocation_status: bool) -> tuple[bool, bool]:
    """Return ``(use_background, complete_on_sse_terminal)`` for invoke_agent."""
    if not report_invocation_status:
        return False, False
    if not foundry_webhook_completion_available():
        return False, True
    # Prefer webhook completion when we have a signing secret from registration
    use_background = has_any_signing_secret()
    return use_background, not use_background
