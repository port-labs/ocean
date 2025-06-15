---
title: Defining Configuration Files
sidebar_label: 📝 Defining Configuration Files
sidebar_position: 2
---

# 📝 Defining Configuration Files

When building an Ocean integration, you'll need to set up three main configuration files. These files define how your integration works, what data it syncs, and how that data is structured in Port. These files are all defined in the `.port` directory in your integration. The files and the directory structure will be created automatically when you created a new integration.

:::info Configuration Files Overview
1. **`spec.yaml`** (Required): Defines your integration's capabilities and required configuration
2. **`blueprints.json`** (Optional): Defines the data structure in Port
3. **`port-app-config.yml`** (Optional): Defines how to map your data to Port's structure
:::

## The `.port` Directory Structure

The `.port` folder is used to provide resources that are used by the Ocean framework when starting up an integration. The folder includes files that are used both in the initial startup of the integration, as well as validate its configuration in every subsequent run.

Here is the standard structure for the `.port` folder:

```text
└── my_new_integration/
    ├── .port/
    │   ├── spec.yml
    │   └── resources/
    │       ├── port-app-config.yml
    │       └── blueprints.json
    └── ...
```

## The `spec.yaml` File

The `spec.yaml` file is the only required configuration file. It defines:
- What kinds of resources your integration can sync
- What configuration variables users need to provide
- Whether your integration supports OAuth
- What features your integration provides

### Location
The `spec.yaml` file is created automatically when you create a new integration. It is located in the `.port` directory in your integration directory.

### Structure
The `spec.yaml` file has several key sections:

#### Integration Base Specification
```yaml
type: myIntegration
description: My integration for Port Ocean
icon: myIntegration
```

This section specifies basic information displayed in Port's UI:
- `type` - integration type, determines the generated image name
- `description` - displayed in Port's UI
- `icon` - must match one of Port's available icons

#### Features Specification
```yaml
features:
  - type: exporter
    section: Project management
    resources:
      - kind: my_integ_kind1
      - kind: my_integ_kind2
```

This section defines integration capabilities:
- `type` - integration type (`exporter` or `gitops`)
- `section` - category (e.g., `GitOps`, `Git Providers`, `Project management`)
- `resources` - array of supported kinds

#### Configuration Validation
```yaml
configurations:
  - name: appHost
    required: false
    type: url
    description: "The host of the Port Ocean app"
  - name: secretToken
    required: true
    type: string
    description: "The token to authenticate with the 3rd party service"
    sensitive: true
```

This section validates user inputs:
- `name` - parameter name in camelCase
- `required` - whether parameter is mandatory
- `type` - parameter type (`string`, `number`, `boolean`, `object`, `array`, `url`)
- `description` - parameter usage explanation
- `sensitive` - whether parameter is secret

Jira's spec.yaml file is shown below to give an idea of how the file is structured.

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

### Key Components
- **`title`**: Your integration's display name
- **`description`**: A brief description of what your integration does
- **`features`**: What your integration can do (usually `exporter`)
- **`resources`**: The types of data your integration can sync
- **`configurations`**: Required environment variables users must provide to run the integration

## The `blueprints.json` File

The `blueprints.json` file defines how your data will be structured in Port. It's optional but recommended for a better user experience.

### Location
The `blueprints.json` file is created automatically when you create a new integration. It is located in the `.port/resources` directory in your integration directory.

### Structure
The `blueprints.json` file is a JSON array of blueprint objects that match Port's API blueprint structure:

```json
[
  {
    "identifier": "myBlueprint",
    "title": "My Blueprint",
    "icon": "Microservice",
    "schema": {
      "properties": {
        "myProp": {
          "title": "My Property",
          "type": "string"
        }
      }
    },
    "relations": {
      "relatedBlueprint": {
        "title": "Related Blueprint",
        "target": "relatedBlueprintIdentifier",
        "required": false,
        "many": false
      }
    }
  }
]
```

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

### Key Components
- **`identifier`**: Unique name for this blueprint in Port
- **`schema.properties`**: Fields that will be available in Port
- **`relations`**: How this resource connects to other resources

:::tip Using the UI to create blueprints
We find that using the UI to create blueprints is a great way to get started. You can use the UI to create blueprints for the resources you would like to support and add them to the `blueprints.json` file as an array of the blueprints objects. This is a great way to get started and then you can start to customize the blueprints to your needs.

You can do this by visiting the [Port UI](https://app.port.io) and navigating to the **Builder** section. From there you can click on the **Blueprints** tab and create a new blueprint.

Once you have created the blueprint, you can copy the JSON object and add it to the `blueprints.json` file.
:::

## The `port-app-config.yml` File

The `port-app-config.yml` file defines how to map your integration's data to Port's structure. It's optional but needed for proper data mapping.

### Location
The `port-app-config.yml` file is created automatically when you create a new integration. It is located in the `.port/resources` directory in your integration directory.

### Structure
The `port-app-config.yml` file defines the default resource mapping. It is used to map the data from the third-party service to the blueprints defined in the `blueprints.json` file.

```yaml
resources:
  - kind: myKind
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .myIdentifierField
          title: .myTitleField
          blueprint: '"myTargetBlueprintIdentifier"'
          properties:
            myProp: .myPropField
```

The **`.port/resources/port-app-config.yml`** file defines the **default resource mapping**. It is used to map the data from the third-party service to the blueprints defined in the `blueprints.json` file. You can find below an example of the file for the Jira integration.

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

### Key Components
- **`selector.query`**: JQ filter to determine which items to sync
- **`mappings`**: How to map your data to Port's structure
- **`properties`**: Field mappings using JQ expressions
- **`relations`**: How to link resources together

## Best Practices

1. **Start Simple**
   - Begin with essential fields only
   - Add more fields as needed
   - Keep mappings straightforward

2. **Document Everything**
   - Add clear descriptions for all fields
   - Explain any special mappings
   - Document required configurations

3. **Test Your Configurations**
   - Verify all mappings work
   - Test with real data
   - Check relations are correct

4. **Handle Updates**
   - Consider backward compatibility
   - Document changes in changelog
   - Test updates thoroughly

:::info Example Implementation
You can find complete examples in the [Jira integration](https://github.com/port-labs/ocean/tree/main/integrations/jira/.port) and [Octopus integration](https://github.com/port-labs/ocean/tree/main/integrations/octopus/.port) repositories.
:::

## Modifying Existing Configurations

Once an integration is running, changes to `blueprints.json` and `port-app-config.yml` won't affect existing installations. To update configurations:

1. Modify from the UI:

   For the blueprints, you can modify them from the UI by following the steps below:
     - Go to the **Builder** section in the [Port UI](https://app.port.io)
     - Click on the **Blueprints** tab
     - Find the blueprint you want to modify and edit it
     - Click on the **Save** button to save the changes

   For the data mapping, you can modify it from the UI by following the steps below:
     - Go to the **Builder** section in the [Port UI](https://app.port.io)
     - Click on the **Data Sources** tab
     - Find the data source you want to modify and edit it
     - Click on the **Save and Resync** button to save the changes

2. Delete existing mapping, data and blueprints using the CLI:
   ```bash
   ocean defaults clean --force --destroy
   ```

3. Or use the API decribe in the [docs](https://docs.port.io/api-reference/delete-an-integration):
   ```
   DELETE /v1/integration/:{identifier}
   ```

