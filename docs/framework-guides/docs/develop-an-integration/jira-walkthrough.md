---
title: Building a Jira Integration
sidebar_label: 🔨 Jira Integration Walkthrough
sidebar_position: 6
---

# 🔨 Building a Jira Integration

This guide walks you through creating a Jira integration for Port using the Ocean framework. We'll cover each step of the process, from initialization to implementation and testing.

## Prerequisites

Before starting, ensure you have:
- Ocean CLI installed
- Python 3.11 or higher
- A Jira instance with API access
- Port account with necessary permissions

## Step 1: Initialize the Integration

First, create a new Ocean integration using the CLI:

```bash showLineNumbers
# Create a new integration
ocean init

# Follow the prompts:
# 1. Choose a name (e.g., "jira")
# 2. Select integration type: "API"
# 3. Choose Python as the language
```

This creates a basic integration structure with necessary files and folders.

## Step 2: Configure the Integration

### Update spec.yml

The `.port/spec.yml` file defines your integration's metadata and requirements:

```yaml showLineNumbers
# .port/spec.yml
kind: Integration
name: jira
description: Sync Jira issues and projects with Port
icon: jira
vendor: atlassian

service:
  image: ghcr.io/port-labs/port-ocean-jira
  secrets:
    - name: JIRA_API_TOKEN
      required: true
    - name: JIRA_USERNAME
      required: true

config:
  schema:
    type: object
    required:
      - baseUrl
    properties:
      baseUrl:
        type: string
        title: Jira Base URL
        description: Your Jira instance URL
```

### Configure config.yaml

Set up your integration configuration:

```yaml showLineNumbers
# config.yaml
integration:
  identifier: my-jira-integration
  type: jira

config:
  baseUrl: "{{ from env JIRA_URL }}"
  username: "{{ from env JIRA_USERNAME }}"
  apiToken: "{{ from env JIRA_API_TOKEN }}"

  # Optional configurations
  projectKeys: ["PROJ1", "PROJ2"]
  maxResults: 100

  eventListener:
    type: "POLLING"
    config:
      interval: 300
```

## Step 3: Implement the Integration

### Create the Main Integration Class

```python showLineNumbers
from typing import AsyncGenerator
from port_ocean.core.handlers.port_app_config import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, ObjectKind

class JiraIntegration(BaseIntegration):
    """Jira integration implementation."""

    class AppConfigHandlerClass(APIPortAppConfig):
        """Configuration handler for Jira integration."""
        pass

    def __init__(self) -> None:
        super().__init__()
        self.client = None
```

### Implement the Jira Client

```python showLineNumbers
from dataclasses import dataclass
from aiohttp import ClientSession
from port_ocean.exceptions.core import IntegrationError

@dataclass
class JiraClient:
    """Client for interacting with Jira API."""

    def __init__(self, base_url: str, username: str, api_token: str) -> None:
        self.base_url = base_url.rstrip('/')
        self.auth = (username, api_token)
        self.session = ClientSession()

    async def get_issues(self, jql: str = '') -> list[dict]:
        """Fetch issues from Jira."""
        url = f"{self.base_url}/rest/api/2/search"
        params = {'jql': jql} if jql else {}

        async with self.session.get(url, params=params, auth=self.auth) as response:
            if response.status != 200:
                raise IntegrationError(f"Failed to fetch Jira issues: {response.status}")
            data = await response.json()
            return data['issues']
```

### Add Resync Methods

```python showLineNumbers
@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(self, kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Jira issues."""
    issues = await self.client.get_issues()

    for issue in issues:
        yield {
            'identifier': issue['key'],
            'title': issue['fields']['summary'],
            'blueprint': 'jiraIssue',
            'properties': {
                'status': issue['fields']['status']['name'],
                'type': issue['fields']['issuetype']['name'],
                'priority': issue['fields']['priority']['name'],
                'assignee': issue['fields']['assignee']['displayName'],
                'reporter': issue['fields']['reporter']['displayName'],
                'created': issue['fields']['created'],
                'updated': issue['fields']['updated']
            }
        }
```

## Step 4: Add Port Resources

### Create Blueprint Definition

```yaml showLineNumbers
# .port/resources/blueprints.json
{
  "identifier": "jiraIssue",
  "title": "Jira Issue",
  "icon": "Jira",
  "schema": {
    "properties": {
      "status": {
        "type": "string",
        "title": "Status"
      },
      "type": {
        "type": "string",
        "title": "Type"
      },
      "priority": {
        "type": "string",
        "title": "Priority"
      },
      "assignee": {
        "type": "string",
        "title": "Assignee"
      },
      "reporter": {
        "type": "string",
        "title": "Reporter"
      },
      "created": {
        "type": "string",
        "format": "date-time",
        "title": "Created At"
      },
      "updated": {
        "type": "string",
        "format": "date-time",
        "title": "Updated At"
      }
    },
    "required": ["status", "type"]
  }
}
```

## Step 5: Validate and Test

1. Run lint checks:
```bash showLineNumbers
make lint
```

2. Verify configuration:
```bash showLineNumbers
# Set required environment variables
export JIRA_URL=https://your-instance.atlassian.net
export JIRA_USERNAME=your-username
export JIRA_API_TOKEN=your-token

# Run the integration locally
ocean integration run
```

## Security Considerations

The Ocean framework ensures:
- Secure handling of credentials
- No inbound network connectivity required
- Data processing occurs on your premises
- Automatic PII and secret key scrubbing

## Next Steps

After implementing your integration:
1. Test thoroughly with your Jira instance
2. Review security settings
3. Deploy the integration
4. Monitor the integration in Port

## Troubleshooting

Common issues and solutions:

1. Authentication Errors
   - Verify API token permissions
   - Check username format
   - Ensure base URL is correct

2. Rate Limiting
   - Adjust polling interval
   - Implement pagination
   - Use JQL filters to limit data

3. Data Sync Issues
   - Check event listener configuration
   - Verify blueprint mappings
   - Review Jira field permissions
