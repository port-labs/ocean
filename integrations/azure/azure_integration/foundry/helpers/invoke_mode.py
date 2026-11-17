from __future__ import annotations


def invoke_agent_completion_mode(*, report_invocation_status: bool) -> bool:
    """Return whether invoke should complete on SSE terminal events.

    When ``reportInvocationStatus`` is false, the run closes on bind
    (``early_complete_on_bind``). When true, complete on SSE terminal; Foundry
    ``response.*`` webhooks may also complete (idempotent) if they arrive first.
    """
    return report_invocation_status
