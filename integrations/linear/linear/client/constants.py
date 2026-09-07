from enum import StrEnum

LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"
PAGE_SIZE = 50

WEBHOOK_NAME = "Port-Ocean-Events-Webhook"
WEBHOOK_EVENTS = [
    "Issue",
    "IssueLabel",
    "Document",
]


class LinearObject(StrEnum):
    TEAMS = "TEAMS"
    LABELS = "LABELS"
    ISSUES = "ISSUES"
    DOCUMENTS = "DOCUMENTS"


CONNECTION_KEYS: dict[LinearObject, str] = {
    LinearObject.TEAMS: "teams",
    LinearObject.LABELS: "issueLabels",
    LinearObject.ISSUES: "issues",
    LinearObject.DOCUMENTS: "documents",
}
