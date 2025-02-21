---
sidebar_position: 5
---


# 📝 Defining Configuration Files
The next step in our integration journey is to define configurations for our integration which are are just three (3):

- `.port/spec.yaml`: A required file used to provide the integration specification and also a validation layer for the inputs required by the integration. The validation layer is used to verify the provided integration configuration during the integration startup process. The [The `spec.yaml` section](https://ocean.port.io/develop-an-integration/integration-spec-and-default-resources#specyaml-file) of the Integration Spec and Defaults documentation gives more details.

- `.port/resources/blueprints.json`: An optional file that is used to provide default resources that will be created when the integration is installed. For more details, see the [`blueprints.json` section](https://ocean.port.io/develop-an-integration/integration-spec-and-default-resources#blueprintsjson-file) of the Integration Spec and Defaults documentation.

- `.port/resources/port-app-config.yml`: An optional file that is used to specify the default integration resource mapping that will be created when the integration is installed. For more details, see the [`port-app-config.yml` section](https://ocean.port.io/develop-an-integration/integration-spec-and-default-resources#port-app-configyml-file) of the Integration Spec and Defaults documentation..


## `spec.yaml` File
For our `spec.yaml` file, we will specify the kinds and the configuration variables the user should provide


<details>

<summary><b>`spec.yaml` file</b></summary>

```yaml showLineNumbers title="spec.yaml"
title: Github
description: GitHub integration for Port Ocean
icon: GitHub
features:
  - type: exporter
    section: Git Providers
    resources:
      - kind: organization
      - kind: repository
      - kind: pull_request
configurations:
  - name: accessToken
    required: false
    type: string
    sensitive: true
    description: Access token for the GitHub API. If not provided, the GitHub API will be accessed anonymously. See the <a target="_blank" href= "https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api?apiVersion=2022-11-28">GitHub Authentication Documentation</a>
  - name: baseUrl
    type: url
    required: false
    default: https://api.github.com
    description: Base URL for the GitHub API. If not provided, the default GitHub API URL, https://api.github.com will be used.

```

</details>


## `blueprints.json` File
For our `blueprints.json` file, we will specify the default blueprints that will be created when the integration is installed.


<details>

<summary><b>`blueprints.json` file</b></summary>

```json showLineNumbers title="spec.yaml"
[
  {
    "identifier": "githubOrganization",
    "title": "Organization",
    "icon": "Github",
    "schema": {
      "properties": {
        "url": {
          "title": "Organization URL",
          "type": "string",
          "format": "url"
        },
        "description": {
          "title": "Description",
          "type": "string"
        },
        "verified": {
          "title": "Verified",
          "type": "boolean"
        }
      }
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {}
  },
  {
    "identifier": "githubRepository",
    "title": "Repository",
    "icon": "Github",
    "schema": {
      "properties": {
        "description": {
          "title": "Description",
          "type": "string"
        },
        "url": {
          "title": "Repository URL",
          "type": "string",
          "format": "url"
        },
        "defaultBranch": {
          "title": "Default branch",
          "type": "string"
        }
      },
      "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {}
  },
  {
    "identifier": "githubPullRequest",
    "title": "Pull Request",
    "icon": "Github",
    "schema": {
      "properties": {
        "creator": {
          "title": "Creator",
          "type": "string"
        },
        "assignees": {
          "title": "Assignees",
          "type": "array"
        },
        "reviewers": {
          "title": "Reviewers",
          "type": "array"
        },
        "status": {
          "title": "Status",
          "type": "string",
          "enum": ["merged", "open", "closed"],
          "enumColors": {
            "merged": "purple",
            "open": "green",
            "closed": "red"
          }
        },
        "closedAt": {
          "title": "Closed At",
          "type": "string",
          "format": "date-time"
        },
        "updatedAt": {
          "title": "Updated At",
          "type": "string",
          "format": "date-time"
        },
        "mergedAt": {
          "title": "Merged At",
          "type": "string",
          "format": "date-time"
        },
        "createdAt": {
          "title": "Created At",
          "type": "string",
          "format": "date-time"
        },
        "link": {
          "format": "url",
          "type": "string"
        },
        "leadTimeHours": {
          "title": "Lead Time in hours",
          "type": "number"
        }
      },
      "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {
      "days_old": {
        "title": "Days Old",
        "icon": "DefaultProperty",
        "calculation": "(now / 86400) - (.properties.createdAt | capture(\"(?<date>\\\\d{4}-\\\\d{2}-\\\\d{2})\") | .date | strptime(\"%Y-%m-%d\") | mktime / 86400) | floor",
        "type": "number"
      }
    },
    "relations": {
      "repository": {
        "title": "Repository",
        "target": "githubRepository",
        "required": false,
        "many": false
      }
    }
  }
]

```

</details>


## `port-app-config.yml` File

For our `port-app-config.yml` file, we will specify the default integration resource mapping that will be created when the integration is installed. In addition, we will specify default organizations data will be ingested from.


<details>

<summary><b>`port-app-config.yml` file</b></summary>

```yaml showLineNumbers title="spec.yaml"
resources:
  - kind: organization
    selector:
      query: "true" # JQ boolean query. If evaluated to false - skip syncing the object.
      organizations:
        - "github"
    port:
      entity:
        mappings:
          identifier: ".name" # The Entity identifier will be the organization name.
          title: ".name"
          blueprint: '"githubOrganization"'
          properties:
            description: .description
            url: .html_url
            verified: .is_verified
  - kind: repository
    selector:
      query: "true" # JQ boolean query. If evaluated to false - skip syncing the object.
      organizations:
        - "github"
      type: "public" # all, public, private, forks, sources, member
    port:
      entity:
        mappings:
          identifier: ".name" # The Entity identifier will be the repository name.
          title: ".name"
          blueprint: '"githubRepository"'
          properties:
            description: .description # fetching the README.md file that is within the root folder of the repository and ingesting its contents as a markdown property
            url: .html_url
            defaultBranch: .default_branch
  - kind: pull_request
    selector:
      query: "true" # JQ boolean query. If evaluated to false - skip syncing the object.
      organizations:
        - "github"
      repositoryType: "public" # all, public, private, forks, sources, member
      state: "all" # all, open, closed
    port:
      entity:
        mappings:
          identifier: ".head.repo.name + (.id|tostring)" # The Entity identifier will be the repository name + the pull request ID.
          title: ".title"
          blueprint: '"githubPullRequest"'
          properties:
            creator: ".user.login"
            assignees: "[.assignees[].login]"
            reviewers: "[.requested_reviewers[].login]"
            status: ".state" # merged, closed, opened
            closedAt: ".closed_at"
            updatedAt: ".updated_at"
            mergedAt: ".merged_at"
            createdAt: ".created_at"
            link: ".html_url"
            leadTimeHours: >-
                (.created_at as $createdAt | .merged_at as $mergedAt |
                ($createdAt | sub("\\..*Z$"; "Z") | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime) as $createdTimestamp |
                ($mergedAt | if . == null then null else sub("\\..*Z$"; "Z") |
                strptime("%Y-%m-%dT%H:%M:%SZ") | mktime end) as $mergedTimestamp |
                if $mergedTimestamp == null then null else
                (((($mergedTimestamp - $createdTimestamp) / 3600) * 100 | floor) / 100) end)

          relations:
            repository: .head.repo.name

```

</details>


:::tip Source Code
You can find the source code for the integration in the [Developing An Integration repository on GitHub](https://github.com/port-labs/developing-an-integration)

:::

Having defined the configuration files, we can now proceed to the publishing our integration.
