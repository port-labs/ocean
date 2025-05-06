GET_EXISTING_CHANNEL_QUERY = """
{
  actor {
    account(id: {{ account_id }}) {
      aiNotifications {
        channels(filters: { name: "{{ channel_name }}" }) {
          entities {
            id
            name
            type
            product
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

CREATE_WEBHOOK_MUTATION = """
mutation {
  aiNotificationsCreateDestination(
    accountId: {{ accountId }},
    destination: {
      type: WEBHOOK,
      name: "{{ name }}",
      {% if auth %}
      auth: {
        type: BASIC,
        basic: {
          user: "port",
          password: "{{ auth.basic.password }}"
        }
      }
      {% endif %}
      properties: [
        {
          key: "url",
          value: "{{ url }}"
        }
      ]
    }
  ) {
    destination {
      id
      name
      type
      properties {
        key
        value
      }
    }
    error {
      ... on AiNotificationsResponseError {
        description
        details
        type
      }
    }
  }
}
"""

CREATE_CHANNEL_MUTATION = """
  mutation {
    aiNotificationsCreateChannel(
      channel: {
        product: IINT,
        properties: {
          key: "payload",
          displayValue: null,
          label: null,
          value: {{ payloadValue }}
        },
        name: "{{ channelName }}",
        destinationId: "{{ destinationId }}",
        type: WEBHOOK
      }
      accountId: {{ accountId }}
    ) {
      channel {
        id
        destinationId
      }
      error {
        ... on AiNotificationsResponseError {
          description
          details
          type
        }
      }
    }
  }
"""

CREATE_WORKFLOW_MUTATION = """
mutation {
    aiWorkflowsCreateWorkflow(
        accountId: {{ accountId }}
        createWorkflowData: {
            name: "{{ workflowName }}"
            destinationConfigurations: {
                channelId: "{{ channelId }}"
                notificationTriggers: [ACTIVATED, ACKNOWLEDGED, CLOSED, PRIORITY_CHANGED, INVESTIGATING, OTHER_UPDATES]
            }
            mutingRulesHandling: DONT_NOTIFY_FULLY_MUTED_ISSUES
            issuesFilter: {
                name: "team specific issues"
                predicates: [
                    {
                        attribute: "accumulations.tag.team"
                        operator: EXACTLY_MATCHES
                        values: ["security"]
                    }
                ]
                type: FILTER
            }
            destinationsEnabled: true
            workflowEnabled: true
        }
    ) {
        workflow {
            id
        }
        errors {
            description
            type
        }
    }
}
"""
