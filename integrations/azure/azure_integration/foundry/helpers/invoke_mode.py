from __future__ import annotations

from port_ocean.context.ocean import ocean


def foundry_webhook_completion_available() -> bool:
    """True when Ocean can receive Foundry ``response.*`` webhooks."""
    if not ocean.app.base_url:
        return False
    if not ocean.app.config.event_listener.should_process_webhooks:
        return False
    return True


def invoke_agent_completion_mode(*, report_invocation_status: bool) -> bool:
    """Return whether invoke should complete on SSE terminal events.

    Invoke always sends ``background=true``. When ``reportInvocationStatus`` is
    false, the run closes on bind (caller sets early_complete_on_bind). When true,
    prefer webhook completion; fall back to SSE if webhooks are unavailable.
    """
    if not report_invocation_status:
        return False
    return not foundry_webhook_completion_available()
