GET_EXISTING_WEBHOOKS_QUERY = """
{
  actor {
    account(id: {{ account_id }}) {
      aiNotifications {
        destinations {
          entities {
            id
            name
            type
            properties {
              key
              value
            }
          }
        }
      }
    }
  }
}
"""

GET_EXISTING_WORKFLOWS_QUERY = """
{
  actor {
    account(id: {{ account_id }}) {
      aiWorkflows {
        workflows(filters: {name: "{{ workflow_name }}"}) {
          entities {
            id
            name
          }
          nextCursor
          totalCount
        }
      }
    }
  }
}
"""

GET_EXISTING_CHANNEL_QUERY = """
{
  actor {
    account(id: {{ account_id }}) {
      aiNotifications {
        channels(filters: { name: "{{ channel_name }}" }) {
          entities {
            id
            name
            destinationId
            properties {
              key
              value
            }
          }
        }
      }
    }
  }
}
"""

GET_ISSUE_ENTITY_GUIDS_QUERY = """
{
  actor {
    account(id: {{ account_id }}) {
      aiIssues {
        issues(filter: {ids: "{{ issue_id }}"}) {
          issues {
            entityGuids
          }
        }
      }
    }
  }
}
"""
