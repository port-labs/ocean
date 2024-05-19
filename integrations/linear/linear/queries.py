QUERIES = {
    "BASE_ISSUES_QUERY_FIELDS": """
    id
    createdAt
    updatedAt
    archivedAt
    number
    title
    priority
    estimate
    sortOrder
    startedAt
    completedAt
    startedTriageAt
    triagedAt
    canceledAt
    autoClosedAt
    autoArchivedAt
    dueDate
    slaStartedAt
    slaBreachesAt
    trashed
    snoozedUntilAt
    labelIds
    previousIdentifiers
    subIssueSortOrder
    priorityLabel
    integrationSourceType
    identifier
    url
    branchName
    customerTicketCount
    description
    descriptionState
    team {
        id
        name
        key
    }
    state {
        name
    }
    creator {
        name
        email
    }
    assignee {
        name
        email
    }
    parent {
        id
        identifier
    }
    """,
    "BASE_LABELS_QUERY_FIELDS": """
    id
    createdAt
    updatedAt
    archivedAt
    name
    description
    color
    isGroup
    parent {
    id
    }
    children{
        edges {
            node {
                id
            }
        }
    }
    """,
    "GET_SINGLE_ISSUE": """
    query Issue {
        issue(id: "{{ issue_identifier }}") {
            {{ base_query_fields }}
        }
    }
    """,
    "GET_SINGLE_LABEL": """
    query IssueLabel {
        issueLabel(id: "{{ label_id }}") {
            {{ base_query_fields }}
        }
    }
    """,
    "GET_ISSUES_PAGE": """
    query Issues {
        issues(first: {{ page_size }}{{ after_cursor }}) {
            edges {
                cursor
                node {
                    {{ base_query_fields }}
                }
            }
            pageInfo {
                hasNextPage
                startCursor
                endCursor
            }
        }
    }
    """,
    "GET_TEAMS_PAGE": """
    query Teams {
        teams(first: {{ page_size }}{{ after_cursor }}) {
            edges {
                cursor
                node {
                    id
                    name
                    key
                    description
                    organization {
                        id
                        name
                        urlKey
                    }
                }
            }
            pageInfo {
                hasNextPage
                startCursor
                endCursor
            }
        }
    }
    """,
    "GET_LABELS_PAGE": """
    query IssueLabels {
        issueLabels(first: {{ page_size }}{{ after_cursor }}) {
            edges {
                cursor
                node {
                    {{ base_query_fields }}
                }
            }
            pageInfo {
                hasNextPage
                startCursor
                endCursor
            }
        }
    }
    """,
    "GET_LIVE_EVENTS_WEBHOOKS": """
    query {
        webhooks {
            nodes {
                id
                url
                label
                enabled
                team {
                    id
                    name
                }
            }
        }
    }
    """,
    "CREATE_LIVE_EVENTS_WEBHOOK": """
    mutation {
        webhookCreate (
            input: {
                label: "{{ webhook_label }}"
                url: "{{ webhook_url }}"
                allPublicTeams: true
                resourceTypes: {{ resource_types|tojson() }}
            }
        ) {
            success
            webhook {
                id
                enabled
            }
        }
    }
    """,
}
