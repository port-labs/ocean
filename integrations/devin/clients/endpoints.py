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
