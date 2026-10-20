SESSIONS = "/sessions"
PLAYBOOKS = "/playbooks"
KNOWLEDGE_NOTES = "/knowledge/notes"
SECRETS = "/secrets"


def session(session_id: str) -> str:
    return f"{SESSIONS}/{session_id}"


def session_messages(session_id: str) -> str:
    return f"{session(session_id)}/messages"


def session_tags(session_id: str) -> str:
    return f"{session(session_id)}/tags"


def session_archive(session_id: str) -> str:
    return f"{session(session_id)}/archive"


def members_users_beta(org_id: str) -> str:
    """Org member lookup lives under v3beta1, not the org-scoped v3 base path."""
    return f"/v3beta1/organizations/{org_id}/members/users"
