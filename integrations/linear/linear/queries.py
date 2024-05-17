QUERIES = {
    "GET_SINGLE_ISSUE": 
    """
    query Issue {
        issue(id: "{{ issue_identifier }}") {
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
        }
    }
    """,
    "GET_SINGLE_LABEL":
    """
    query IssueLabel {
        issueLabel(id: "{{ label_id }}") {
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
        }
    }
    """,
    "GET_FIRST_ISSUES_PAGE":
    """
    query Issues {
        issues(first: {{ page_size }}) {
            edges {
                cursor
                node {
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
    "GET_NEXT_ISSUES_PAGE":
    """
    query Issues {
        issues(first: {{ page_size }}, after: "{{ end_cursor }}") {
            edges {
                cursor
                node {
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
    "GET_FIRST_TEAMS_PAGE":
    """
    query Teams {
        teams(first: {{ page_size }}) {
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
    "GET_NEXT_TEAMS_PAGE":
    """
    query Teams {
        teams(first: {{ page_size }}, after: "{{ end_cursor }}") {
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
    "GET_FIRST_LABELS_PAGE":
    """
    query IssueLabels {
        issueLabels(first: {{ page_size }}) {
            edges {
                cursor
                node {
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
    "GET_NEXT_LABELS_PAGE":
    """
    query IssueLabels {
        issueLabels(first: {{ page_size }}, after: "{{ end_cursor }}") {
            edges {
                cursor
                node {
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
    "GET_LIVE_EVENTS_WEBHOOKS":
    """
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
    "CREATE_LIVE_EVENTS_WEBHOOK":
    """
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
    """
}