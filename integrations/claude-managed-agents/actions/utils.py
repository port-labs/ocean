EXTERNAL_ID_PREFIX = "claude_session"


def build_external_id(session_id: str, user_message_event_id: str) -> str:
    """Build the Port externalRunId used to correlate session webhooks to runs."""
    return f"{EXTERNAL_ID_PREFIX}_{session_id}_{user_message_event_id}"


def build_session_link(session_id: str) -> str:
    """Build a best-effort console link to the session for run output."""
    return f"https://console.anthropic.com/sessions/{session_id}"
