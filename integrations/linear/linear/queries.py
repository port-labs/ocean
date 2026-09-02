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
    "BASE_DOCUMENTS_QUERY_FIELDS": """
    id
    title
    summary
    icon
    color
    slugId
    url
    content
    documentContentId
    createdAt
    updatedAt
    archivedAt
    hiddenAt
    trashed
    sortOrder
    creator {
        id
        name
        email
    }
    owner {
        id
        name
        email
    }
    updatedBy {
        id
        name
        email
    }
    lastAppliedTemplate {
        id
        name
    }
    project {
        id
        name
    }
    initiative {
        id
        name
    }
    team {
        id
        name
        key
    }
    issue {
        id
        identifier
        title
    }
    release {
        id
    }
    cycle {
        id
        number
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
    "BASE_USERS_QUERY_FIELDS": """
    id
    name
    displayName
    email
    active
    admin
    guest
    url
    avatarUrl
    title
    createdAt
    updatedAt
    """,
    "BASE_PROJECTS_QUERY_FIELDS": """
    id
    name
    description
    url
    progress
    health
    priority
    priorityLabel
    startDate
    targetDate
    slugId
    createdAt
    updatedAt
    status {
        name
        type
    }
    lead {
        id
        name
        email
    }
    teams {
        nodes {
            id
            key
            name
        }
    }
    """,
    "BASE_CYCLES_QUERY_FIELDS": """
    id
    number
    name
    description
    startsAt
    endsAt
    completedAt
    progress
    isActive
    isFuture
    isPast
    createdAt
    updatedAt
    team {
        id
        key
        name
    }
    """,
    "BASE_TEAM_MEMBERSHIPS_QUERY_FIELDS": """
    id
    owner
    createdAt
    updatedAt
    team {
        id
        key
        name
    }
    user {
        id
        name
        email
        displayName
    }
    """,
    "GET_SINGLE_ISSUE": """
    query Issue {
        issue(id: "{{ issue_identifier }}") {
            {{ base_query_fields }}
        }
    }
    """,
    "GET_SINGLE_DOCUMENT": """
    query Document {
        document(id: "{{ document_id }}") {
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
    "GET_DOCUMENTS_PAGE": """
    query Documents {
        documents(first: {{ page_size }}{{ after_cursor }}, includeArchived: false) {
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
    "GET_USERS_PAGE": """
    query Users {
        users(first: {{ page_size }}{{ after_cursor }}) {
            nodes {
                {{ base_query_fields }}
            }
            pageInfo {
                hasNextPage
                startCursor
                endCursor
            }
        }
    }
    """,
    "GET_PROJECTS_PAGE": """
    query Projects {
        projects(first: {{ page_size }}{{ after_cursor }}) {
            nodes {
                {{ base_query_fields }}
            }
            pageInfo {
                hasNextPage
                startCursor
                endCursor
            }
        }
    }
    """,
    "GET_CYCLES_PAGE": """
    query Cycles {
        cycles(first: {{ page_size }}{{ after_cursor }}) {
            nodes {
                {{ base_query_fields }}
            }
            pageInfo {
                hasNextPage
                startCursor
                endCursor
            }
        }
    }
    """,
    "GET_TEAM_MEMBERSHIPS_PAGE": """
    query TeamMemberships {
        teamMemberships(first: {{ page_size }}{{ after_cursor }}) {
            nodes {
                {{ base_query_fields }}
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
    "UPDATE_LIVE_EVENTS_WEBHOOK": """
    mutation {
        webhookUpdate(
            id: "{{ webhook_id }}"
            input: {
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
