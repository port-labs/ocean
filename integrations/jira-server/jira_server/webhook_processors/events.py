from typing import List

JiraDeletedIssueEvent: str = "jira:issue_deleted"
JiraDeletedProjectEvent: str = "project_deleted"
JiraDeletedUserEvent: str = "user_deleted"

JiraIssueEvents: List[str] = [
    "jira:issue_created",
    "jira:issue_updated",
    JiraDeletedIssueEvent,
]

JiraProjectEvents: List[str] = [
    "project_created",
    "project_updated",
    JiraDeletedProjectEvent,
]

JiraUserEvents: List[str] = [
    "user_created",
    "user_updated",
    JiraDeletedUserEvent,
]
