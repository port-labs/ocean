from __future__ import annotations

from port_ocean.context.ocean import ocean


def foundry_webhook_completion_available() -> bool:
    """True when Ocean can receive and verify Foundry ``response.*`` webhooks."""
    if not ocean.app.base_url:
        return False
    if not ocean.app.config.event_listener.should_process_webhooks:
        return False
    config = ocean.integration_config or {}
    secret = config.get("webhookSigningSecret") or config.get("webhook_signing_secret")
    return bool(secret)


def invoke_agent_completion_mode(*, report_invocation_status: bool) -> tuple[bool, bool]:
    """Return ``(use_background, complete_on_sse_terminal)`` for invoke_agent."""
    webhook_ok = foundry_webhook_completion_available()
    use_background = report_invocation_status and webhook_ok
    complete_on_sse_terminal = report_invocation_status and not webhook_ok
    return use_background, complete_on_sse_terminal
