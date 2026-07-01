EXTERNAL_ID_PREFIX = "claude_session"


def build_external_id(session_id: str, user_message_event_id: str) -> str:
    """Build the Port externalRunId used to correlate session webhooks to runs."""
    return f"{EXTERNAL_ID_PREFIX}_{session_id}_{user_message_event_id}"


def build_session_link(workspace_id: str | None, session_id: str) -> str:
    """Build a best-effort console link to the session for run output.

    Falls back to the console root if the workspace id wasn't captured (e.g.
    the anthropic-workspace-id header was unexpectedly absent).
    """
    if not workspace_id:
        return "https://platform.claude.com/"
    return (
        f"https://platform.claude.com/workspaces/{workspace_id}/sessions/{session_id}"
    )
