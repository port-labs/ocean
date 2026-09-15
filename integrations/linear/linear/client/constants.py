from dataclasses import dataclass
from enum import StrEnum

LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"
PAGE_SIZE = 50

WEBHOOK_NAME = "Port-Ocean-Events-Webhook"
WEBHOOK_PATH_SUFFIX = "/integration/webhook"
WEBHOOK_EVENTS = [
    "Issue",
    "IssueLabel",
    "Document",
    "User",
    "Project",
    "Cycle",
]
GET_LIVE_EVENTS_WEBHOOKS_QUERY = "GET_LIVE_EVENTS_WEBHOOKS"
CREATE_LIVE_EVENTS_WEBHOOK_QUERY = "CREATE_LIVE_EVENTS_WEBHOOK"
UPDATE_LIVE_EVENTS_WEBHOOK_QUERY = "UPDATE_LIVE_EVENTS_WEBHOOK"
WEBHOOK_UPDATED_LOG = "Ocean real time reporting webhook already exists and was updated"
WEBHOOK_CREATED_LOG = "Ocean real time reporting webhook created"


@dataclass(frozen=True)
class SingleResourceConfig:
    query_key: str
    response_key: str
    id_param: str
    log_label: str


class LinearObject(StrEnum):
    TEAMS = "TEAMS"
    LABELS = "LABELS"
    ISSUES = "ISSUES"
    DOCUMENTS = "DOCUMENTS"
    USERS = "USERS"
    PROJECTS = "PROJECTS"
    CYCLES = "CYCLES"
    TEAM_MEMBERSHIPS = "TEAM_MEMBERSHIPS"


CONNECTION_KEYS: dict[LinearObject, str] = {
    LinearObject.TEAMS: "teams",
    LinearObject.LABELS: "issueLabels",
    LinearObject.ISSUES: "issues",
    LinearObject.DOCUMENTS: "documents",
    LinearObject.USERS: "users",
    LinearObject.PROJECTS: "projects",
    LinearObject.CYCLES: "cycles",
    LinearObject.TEAM_MEMBERSHIPS: "teamMemberships",
}

NODE_PAGINATION_OBJECTS: frozenset[LinearObject] = frozenset(
    {
        LinearObject.USERS,
        LinearObject.PROJECTS,
        LinearObject.CYCLES,
        LinearObject.TEAM_MEMBERSHIPS,
    }
)

SINGLE_RESOURCE_CONFIG: dict[LinearObject, SingleResourceConfig] = {
    LinearObject.ISSUES: SingleResourceConfig(
        query_key="GET_SINGLE_ISSUE",
        response_key="issue",
        id_param="issue_identifier",
        log_label="issue",
    ),
    LinearObject.DOCUMENTS: SingleResourceConfig(
        query_key="GET_SINGLE_DOCUMENT",
        response_key="document",
        id_param="document_id",
        log_label="document",
    ),
    LinearObject.LABELS: SingleResourceConfig(
        query_key="GET_SINGLE_LABEL",
        response_key="issueLabel",
        id_param="label_id",
        log_label="label",
    ),
    LinearObject.USERS: SingleResourceConfig(
        query_key="GET_SINGLE_USER",
        response_key="user",
        id_param="user_id",
        log_label="user",
    ),
    LinearObject.PROJECTS: SingleResourceConfig(
        query_key="GET_SINGLE_PROJECT",
        response_key="project",
        id_param="project_id",
        log_label="project",
    ),
    LinearObject.CYCLES: SingleResourceConfig(
        query_key="GET_SINGLE_CYCLE",
        response_key="cycle",
        id_param="cycle_id",
        log_label="cycle",
    ),
}
