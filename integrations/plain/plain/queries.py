LIST_COMPANIES = """
query ListCompanies($first: Int, $after: String) {
  companies(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        name
        domainName
        createdAt {
          iso8601
        }
        updatedAt {
          iso8601
        }
      }
    }
  }
}
""".strip()

LIST_TENANTS = """
query ListTenants($first: Int, $after: String) {
  tenants(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
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
      }
    }
  }
}
""".strip()

LIST_USERS = """
query ListUsers($first: Int, $after: String) {
  users(first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
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
      }
    }
  }
}
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


def _indent(selection: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in selection.splitlines())


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

THREAD_TIMELINE = """
query ThreadTimeline($threadId: ID!, $first: Int, $after: String) {
  thread(threadId: $threadId) {
    timelineEntries(first: $first, after: $after) {
      pageInfo {
        hasNextPage
        endCursor
      }
      edges {
        node {
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
        }
      }
    }
  }
}
""".strip()

THREAD_DISCUSSIONS = """
query ThreadDiscussions($threadId: ID!, $first: Int, $after: String) {
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
      }
    }
  }
}
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
