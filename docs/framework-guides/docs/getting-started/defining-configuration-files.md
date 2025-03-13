---
sidebar_position: 4
---

# 📝 Defining Configuration Files

The next step in our integration journey is to define the configurations for our Jira integration. There are three configuration files used by Ocean:

1. **`.port/spec.yaml`**: A required file providing the integration’s specification—defines which kinds exist (in this case, only **project** and **issue**) and which configuration variables are needed at startup.
2. **`.port/resources/blueprints.json`** (optional): Defines default “blueprints” (i.e., entity templates in Port) that will be automatically created when the integration is installed.
3. **`.port/resources/port-app-config.yml`** (optional): Defines the default resource mapping (i.e., how the fetched Jira data maps into Port entities).

For more details on these files, see the [Integration Spec and Defaults documentation](https://ocean.port.io/develop-an-integration/integration-spec-and-default-resources).

## `spec.yaml` File

In the `.port/spec.yaml` file, specify the **project** and **issue** kinds, plus any configuration variables that the user must provide (like `jiraHost`, `atlassianUserEmail`, etc.).

<details>

<summary><b>`spec.yaml` file (Click to expand)</b></summary>

```yaml showLineNumber
title: Jira
description: Jira integration for Port Ocean
icon: Jira
docs: https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/jira
features:
  - type: exporter
    section: Project management
    resources:
      - kind: project
      - kind: issue

configurations:
  - name: jiraHost
    required: true
    type: string
    description: "The URL of your Jira, for example: https://example.atlassian.net"
    sensitive: false

  - name: atlassianUserEmail
    required: true
    type: string
    description: "The email of the user used to query Jira"
    sensitive: true

  - name: atlassianUserToken
    required: true
    type: string
    description: >-
      You can configure the user token on the <a target="_blank" href="https://id.atlassian.com/manage-profile/security/api-tokens">Atlassian account page</a>
    sensitive: true

  - name: atlassianOrganizationId
    required: false
    type: string
    description: >-
      To sync additional data such as teams, your Atlassian Organization ID is required.
      Read
      <a target="_blank" href="https://confluence.atlassian.com/jirakb/what-it-is-the-organization-id-and-where-to-find-it-1207189876.html">How to find your Atlassian Organization ID</a>

saas:
  enabled: true
  liveEvents:
    enabled: true
  oauthConfiguration:
    requiredSecrets:
      - name: atlassianUserEmail
        value: '.oauthData.profile.email'
        description: '"Email for Jira OAuth2 integration"'
      - name: atlassianUserToken
        value: '.oauthData.accessToken'
        description: '"Access Token for Jira OAuth2 integration"'
    valuesOverride:
      integrationSpec:
        jiraHost: '"https://api.atlassian.com/ex/jira/" + .oauthData.profile.accessibleResources[0].id'
      appSpec:
        minimumScheduledResyncInterval: '2h'
```

</details>

**Key Points**

- **`resources: [project, issue]`**: Only these two kinds will be synced.
- **`configurations`**: Your Jira host, user email, and token are required to authenticate.
- **`saas.oauthConfiguration`**: Additional instructions for using OAuth if you choose Atlassian’s newer `api.atlassian.com` approach.

## `blueprints.json` File

The **`.port/resources/blueprints.json`** file defines the **blueprints**—essentially the data structures for your **Jira project** and **Jira issue**.


<details>

<summary><b>`blueprints.json` file (Click to expand)</b></summary>

```json
[
  {
    "identifier": "jiraProject",
    "title": "Jira Project",
    "icon": "Jira",
    "description": "A Jira project",
    "schema": {
      "properties": {
        "url": {
          "title": "Project URL",
          "type": "string",
          "format": "url",
          "description": "URL to the project in Jira"
        },
        "totalIssues": {
          "title": "Total Issues",
          "type": "number",
          "description": "The total number of issues in the project"
        }
      }
    },
    "calculationProperties": {}
  },
  {
    "identifier": "jiraIssue",
    "title": "Jira Issue",
    "icon": "Jira",
    "schema": {
      "properties": {
        "url": {
          "title": "Issue URL",
          "type": "string",
          "format": "url",
          "description": "URL to the issue in Jira"
        },
        "status": {
          "title": "Status",
          "type": "string",
          "description": "The status of the issue"
        },
        "issueType": {
          "title": "Type",
          "type": "string",
          "description": "The type of the issue"
        },
        "components": {
          "title": "Components",
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "The components related to this issue"
        },
        "creator": {
          "title": "Creator",
          "type": "string",
          "description": "The user that created the issue"
        },
        "priority": {
          "title": "Priority",
          "type": "string",
          "description": "The priority of the issue"
        },
        "labels": {
          "items": {
            "type": "string"
          },
          "title": "Labels",
          "type": "array"
        },
        "created": {
          "title": "Created At",
          "type": "string",
          "description": "The created datetime of the issue",
          "format": "date-time"
        },
        "updated": {
          "title": "Updated At",
          "type": "string",
          "description": "The updated datetime of the issue",
          "format": "date-time"
        },
        "resolutionDate": {
          "title": "Resolved At",
          "type": "string",
          "description": "The datetime the issue changed to a resolved state",
          "format": "date-time"
        }
      }
    },
    "calculationProperties": {
      "handlingDuration": {
        "title": "Handling Duration (Days)",
        "icon": "Clock",
        "description": "Time in days from issue creation to resolution",
        "calculation": "if (.properties.resolutionDate != null and .properties.created != null) then ((.properties.resolutionDate[0:19] + \"Z\" | fromdateiso8601) - (.properties.created[0:19] + \"Z\" | fromdateiso8601)) / 86400 else null end",
        "type": "number"
      }
    },
    "relations": {
      "project": {
        "target": "jiraProject",
        "title": "Project",
        "description": "The Jira project containing this issue",
        "required": false,
        "many": false
      }
    }
  }
]
```

</details>

**Key Points**

- **`identifier`**: The name for each blueprint in Port. Here we have `jiraProject` and `jiraIssue`.
- **`schema.properties`**: The fields each entity can have (URL, status, etc.).
- **`relations`**: An issue has a `project` relation, referencing the blueprint `"jiraProject"`.


## `port-app-config.yml` File

This file specifies the **default resource mapping**. In other words, how your **Jira data** (retrieved by the integration) maps to the **blueprints** above. For instance:

1. **`kind: project`**: Tells Ocean how to map a Jira project’s JSON fields into `.port/resources/blueprints.json` fields (like `identifier`, `title`, `url`, etc.).
2. **`kind: issue`**: Tells Ocean how to map a Jira issue’s fields (`status`, `created`, etc.) and references back to `project` as a relation.


<details>

<summary><b>`port-app-config.yml` file (Click to expand)</b></summary>

```yaml showLineNumbers
createMissingRelatedEntities: true
deleteDependentEntities: true

resources:
  - kind: project
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .key
          title: .name
          blueprint: '"jiraProject"'
          properties:
            url: (.self | split("/") | .[:3] | join("/")) + "/projects/" + .key
            totalIssues: .insight.totalIssueCount

  - kind: issue
    selector:
      query: "true"
      jql: "(statusCategory != Done) OR (created >= -1w) OR (updated >= -1w)"
    port:
      entity:
        mappings:
          identifier: .key
          title: .fields.summary
          blueprint: '"jiraIssue"'
          properties:
            url: (.self | split("/") | .[:3] | join("/")) + "/browse/" + .key
            status: .fields.status.name
            issueType: .fields.issuetype.name
            components: .fields.components
            creator: .fields.creator.emailAddress
            priority: .fields.priority.name
            labels: .fields.labels
            created: .fields.created
            updated: .fields.updated
            resolutionDate: .fields.resolutiondate
          relations:
            project: .fields.project.key

```

</details>

**Key Points**

- **`selector.query: \"true\"`**: A simple JQ filter that, if `false`, would skip syncing the item.
- **`properties: ...`**: You can see how data from the Jira API (like `.fields.status.name`) maps to blueprint properties (like `status`).
- **`relations.project`**: Uses the project key `.fields.project.key` to link issues back to the `jiraProject` blueprint.


## Modifying integration configurations (`blueprints.json` and `port-app-config.yml`)
The `blueprints.json` and `port-app-config.yml` files are used to define the structure of the data that will be synced to Port. You can modify these files to include additional fields or relations as needed. Once the integration is run for the first time, these configurations will be synced to Port; any further modifications on the file will not take any effect on existing integrations. Instead, you can modify the configurations directly on Port.

If you would like to update the mapping for an integration, you can do the following:
- Delete existing mapping using the API endpoint `DELETE /api/v1/integrations/{integration_id}/configurations`
- Use the CLI command:

```console
ocean defaults clean --force --destroy
```

Note that this command removes all default mappings and blueprints.

Some best practices to keep in mind when modifying configurations are:
- Verify existing mappings before expecting changes from `port-app-config.yml`.
- Manual changes in the Portal UI may be lost when cleaning defaults.
- Document manual modifications separately to avoid confusion.

For more details, refer to the [Ocean configuration documentation](https://ocean.port.io/develop-an-integration/integration-spec-and-default-resources#port-app-configyml-file). This section explains the structure of the .port folder and its different components.



:::info Source Code
You can find the source code for the integration in the [Jira integration directory on GitHub](https://github.com/port-labs/ocean/tree/main/integrations/jira)

:::

With these configuration files in place, your integration is primed to publish, allowing Ocean to sync and display Jira **projects** and **issues**.
