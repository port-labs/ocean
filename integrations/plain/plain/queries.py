_COMPANY_FIELDS = """
id
name
domainName
createdAt {
  iso8601
}
updatedAt {
  iso8601
}
""".strip()

_TENANT_FIELDS = """
id
externalId
name
url
createdAt {
  iso8601
}
updatedAt {
  iso8601
}
""".strip()

_USER_FIELDS = """
id
fullName
publicName
email
status
role {
  id
  name
  key
}
""".strip()

_MACHINE_USER_FIELDS = """
id
fullName
publicName
description
type
isCustomAgent
isAssignableToThreads
isDeleted
createdAt {
  iso8601
}
updatedAt {
  iso8601
}
""".strip()


def _indent(selection: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in selection.splitlines())


LIST_COMPANIES = f"""
query ListCompanies($first: Int, $after: String) {{
  companies(first: $first, after: $after) {{
    pageInfo {{
      hasNextPage
      endCursor
    }}
    edges {{
      node {{
{_indent(_COMPANY_FIELDS, 8)}
      }}
    }}
  }}
}}
""".strip()

GET_COMPANY = f"""
query GetCompany($companyId: ID!) {{
  company(companyId: $companyId) {{
{_indent(_COMPANY_FIELDS, 4)}
  }}
}}
""".strip()

LIST_TENANTS = f"""
query ListTenants($first: Int, $after: String) {{
  tenants(first: $first, after: $after) {{
    pageInfo {{
      hasNextPage
      endCursor
    }}
    edges {{
      node {{
{_indent(_TENANT_FIELDS, 8)}
      }}
    }}
  }}
}}
""".strip()

GET_TENANT = f"""
query GetTenant($tenantId: ID!) {{
  tenant(tenantId: $tenantId) {{
{_indent(_TENANT_FIELDS, 4)}
  }}
}}
""".strip()

LIST_USERS = f"""
query ListUsers($first: Int, $after: String) {{
  users(first: $first, after: $after) {{
    pageInfo {{
      hasNextPage
      endCursor
    }}
    edges {{
      node {{
{_indent(_USER_FIELDS, 8)}
      }}
    }}
  }}
}}
""".strip()

GET_USER = f"""
query GetUser($userId: ID!) {{
  user(userId: $userId) {{
{_indent(_USER_FIELDS, 4)}
  }}
}}
""".strip()

LIST_MACHINE_USERS = f"""
query ListMachineUsers($first: Int, $after: String) {{
  machineUsers(first: $first, after: $after) {{
    pageInfo {{
      hasNextPage
      endCursor
    }}
    edges {{
      node {{
{_indent(_MACHINE_USER_FIELDS, 8)}
      }}
    }}
  }}
}}
""".strip()

GET_MACHINE_USER = f"""
query GetMachineUser($machineUserId: ID!) {{
  machineUser(machineUserId: $machineUserId) {{
{_indent(_MACHINE_USER_FIELDS, 4)}
  }}
}}
""".strip()

_CUSTOMER_FIELDS = """
id
externalId
fullName
shortName
email {
  email
}
company {
  id
}
tenantMemberships(first: 100) {
  edges {
    node {
      tenant {
        id
      }
    }
  }
}
createdAt {
  iso8601
}
updatedAt {
  iso8601
}
""".strip()

_THREAD_FIELDS = """
id
ref
externalId
title
description
status
priority
customer {
  id
}
tenant {
  id
}
tier {
  id
  name
}
assignedTo {
  __typename
  ... on User {
    id
  }
  ... on MachineUser {
    id
  }
  ... on System {
    id
  }
}
labels {
  id
  labelType {
    id
    name
  }
}
threadFields {
  id
  key
  type
  stringValue
  booleanValue
  numberValue
}
createdAt {
  iso8601
}
updatedAt {
  iso8601
}
""".strip()


LIST_CUSTOMERS = f"""
query ListCustomers($first: Int, $after: String) {{
  customers(first: $first, after: $after) {{
    pageInfo {{
      hasNextPage
      endCursor
    }}
    edges {{
      node {{
{_indent(_CUSTOMER_FIELDS, 8)}
      }}
    }}
  }}
}}
""".strip()

GET_CUSTOMER = f"""
query GetCustomer($customerId: ID!) {{
  customer(customerId: $customerId) {{
{_indent(_CUSTOMER_FIELDS, 4)}
  }}
}}
""".strip()

LIST_THREADS = f"""
query ListThreads($first: Int, $after: String, $filters: ThreadsFilter) {{
  threads(first: $first, after: $after, filters: $filters) {{
    pageInfo {{
      hasNextPage
      endCursor
    }}
    edges {{
      node {{
{_indent(_THREAD_FIELDS, 8)}
      }}
    }}
  }}
}}
""".strip()

GET_THREAD = f"""
query GetThread($threadId: ID!) {{
  thread(threadId: $threadId) {{
{_indent(_THREAD_FIELDS, 4)}
  }}
}}
""".strip()

LIST_THREAD_IDS = """
query ListThreadIds($first: Int, $after: String, $filters: ThreadsFilter) {
  threads(first: $first, after: $after, filters: $filters) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
      }
    }
  }
}
""".strip()

_TIMELINE_ENTRY_FIELDS = """
id
threadId
timestamp {
  iso8601
}
llmText
actor {
  __typename
  ... on UserActor {
    user {
      id
    }
  }
  ... on CustomerActor {
    customer {
      id
    }
  }
  ... on MachineUserActor {
    machineUser {
      id
    }
  }
}
entry {
  __typename
}
""".strip()

_DISCUSSION_FIELDS = """
id
threadId
title
status
agentStatus
visibility
isUnread
createdAt {
  iso8601
}
updatedAt {
  iso8601
}
lastActivityAt {
  iso8601
}
resolvedAt {
  iso8601
}
channelDetails {
  __typename
  ... on ThreadDiscussionSlackChannelDetails {
    slackChannelName
    slackMessageLink
  }
  ... on ThreadDiscussionEmailChannelDetails {
    emailRecipients
  }
}
createdBy {
  __typename
  ... on UserActor {
    userId
  }
  ... on CustomerActor {
    customerId
  }
  ... on MachineUserActor {
    machineUserId
  }
  ... on SystemActor {
    systemId
  }
}
""".strip()

THREAD_TIMELINE = f"""
query ThreadTimeline($threadId: ID!, $first: Int, $after: String) {{
  thread(threadId: $threadId) {{
    timelineEntries(first: $first, after: $after) {{
      pageInfo {{
        hasNextPage
        endCursor
      }}
      edges {{
        node {{
{_indent(_TIMELINE_ENTRY_FIELDS, 10)}
        }}
      }}
    }}
  }}
}}
""".strip()

GET_TIMELINE_ENTRY = f"""
query GetTimelineEntry($customerId: ID!, $timelineEntryId: ID!) {{
  timelineEntry(customerId: $customerId, timelineEntryId: $timelineEntryId) {{
{_indent(_TIMELINE_ENTRY_FIELDS, 4)}
  }}
}}
""".strip()

THREAD_DISCUSSIONS = f"""
query ThreadDiscussions($threadId: ID!, $first: Int, $after: String) {{
  discussions(
    first: $first
    after: $after
    filters: {{ threadIds: [$threadId] }}
  ) {{
    pageInfo {{
      hasNextPage
      endCursor
    }}
    edges {{
      node {{
{_indent(_DISCUSSION_FIELDS, 8)}
      }}
    }}
  }}
}}
""".strip()

GET_DISCUSSION = f"""
query GetDiscussion($discussionId: ID!) {{
  discussion(discussionId: $discussionId) {{
{_indent(_DISCUSSION_FIELDS, 4)}
  }}
}}
""".strip()

THREAD_DISCUSSION_IDS = """
query ThreadDiscussionIds($threadId: ID!, $first: Int, $after: String) {
  discussions(
    first: $first
    after: $after
    filters: { threadIds: [$threadId] }
  ) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        channelDetails {
          __typename
        }
      }
    }
  }
}
""".strip()

DISCUSSION_MESSAGES = """
query DiscussionMessages($discussionId: ID!, $first: Int, $after: String) {
  discussion(discussionId: $discussionId) {
    threadId
    messages(first: $first, after: $after) {
      pageInfo {
        hasNextPage
        endCursor
      }
      edges {
        node {
          id
          threadDiscussionId
          type
          text
          slackMessageLink
          createdAt {
            iso8601
          }
          createdBy {
            __typename
            ... on UserActor {
              userId
            }
            ... on CustomerActor {
              customerId
            }
            ... on MachineUserActor {
              machineUserId
            }
            ... on SystemActor {
              systemId
            }
          }
        }
      }
    }
  }
}
""".strip()

LIST_WEBHOOK_TARGETS = """
query ListWebhookTargets($first: Int, $after: String) {
  webhookTargets(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        url
        description
        isEnabled
        version
        eventSubscriptions {
          eventType
        }
      }
    }
  }
}
""".strip()

CREATE_WEBHOOK_TARGET = """
mutation CreateWebhookTarget($input: CreateWebhookTargetInput!) {
  createWebhookTarget(input: $input) {
    webhookTarget {
      id
      url
      description
      isEnabled
      version
    }
    error {
      message
      type
      code
    }
  }
}
""".strip()

UPDATE_WEBHOOK_TARGET = """
mutation UpdateWebhookTarget($input: UpdateWebhookTargetInput!) {
  updateWebhookTarget(input: $input) {
    webhookTarget {
      id
      url
      description
      isEnabled
      version
    }
    error {
      message
      type
      code
    }
  }
}
""".strip()
