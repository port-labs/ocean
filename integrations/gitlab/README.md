# gitlab

Gitlab integration for Port using Port-Ocean Framework

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)

## Installation
For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration at your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.secrets.tokenMapping: Mapping of Gitlab tokens to Port Ocean tokens. example: {"THE_GROUP_TOKEN":["getport-labs/**", "GROUP/PROJECT PATTERN TO RUN FOR"]}
# integration.config.appHost: The host of the Port Ocean app. Used for setting up the webhooks against the Gitlab.
# ingress.annotations."nginx\.ingress\.kubernetes\.io/rewrite-target": Change the annotation value and key to match your ingress controller

helm upgrade --install my-gitlab-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
	--set integration.identifier="my-gitlab-integration"  \
	--set integration.type="gitlab"  \
	--set integration.triggerChannel.type="SAMPLE"  \
	--set integration.secrets.tokenMapping="\{\"TOKEN\": [\"GROUP_NAME/**\"]\}"  \
	--set integration.config.appHost="https://example.com"  \
	--set ingress.enabled=true  \
	--set ingress.annotations."nginx\.ingress\.kubernetes\.io/rewrite-target"= / 
```

## Supported Kinds
### Project 

The mapping should refer to on of the projects from the example response: [Gitlab documentation](https://docs.gitlab.com/ee/api/groups.html#list-a-groups-projects)

<details>
<summary>blueprint.json</summary>

```json
{
  "identifier": "microservice",
  "title": "Microservice",
  "icon": "Service",
  "schema": {
    "properties": {
      "url": {
        "title": "URL",
        "format": "url",
        "type": "string"
      },
      "description": {
        "title": "Description",
        "type": "string"
      },
      "namespace": {
        "title": "Namespace",
        "type": "string"
      },
      "full_path": {
        "title": "Full Path",
        "type": "string"
      }
    }
  }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: project
    selector:
      query: 'true'
    port:
    entity:
      mappings:
        identifier: .namespace.full_path | gsub("/";"-")
        title: .name
        blueprint: '"microservice"'
        properties:
          url: .web_link
          description: .description
          namespace: .namespace.name
          full_path: .namespace.full_path | split("/") | .[:-1] | join("/")
```
</details>

### Issue 

The mapping should refer to one of the issues in the example response: [Gitlab documentation](https://docs.gitlab.com/ee/api/issues.html#list-project-issues)

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier": "issue",
    "title": "Issue",
    "icon": "GitLab",
    "schema": {
      "properties": {
        "link": {
          "title": "Link",
          "type": "string",
          "format": "url"
        },
        "description": {
          "title": "Description",
          "type": "string",
          "format": "markdown"
        },
        "createdAt": {
          "title": "Created At",
          "type": "string",
          "format": "date-time"
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
        "creator": {
          "title": "Creator",
          "type": "string"
        },
        "status": {
          "title": "Status",
          "type": "string",
          "enum": [
            "opened",
            "closed"
          ],
          "enumColors": {
            "opened": "green",
            "closed": "purple"
          }
        },
        "labels": {
          "title": "Labels",
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      }
    }
  }
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: issue
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id | tostring
          title: .title
          blueprint: '"issue"'
          properties:
            creator: .author.name
            status: .state
            createdAt: .created_at
            closedAt: .closed_at
            updatedAt: .updated_at
            description: .description
            link: .web_url
            labels: '[.labels[]]'
```
</details>

### Merge Request 

The mapping should refer to on of the merge requests from the example response: [Gitlab documentation](https://docs.gitlab.com/ee/api/merge_requests.html#list-project-merge-requests)

<details>
<summary>blueprint.json</summary>

```json
{
  "identifier": "mergeRequest",
  "title": "Merge Request",
  "icon": "GitVersion",
  "schema": {
    "properties": {
      "creator": {
        "title": "Creator",
        "type": "string"
      },
      "status": {
        "title": "Status",
        "type": "string",
        "enum": [
          "opened",
          "closed",
          "merged",
          "locked"
        ],
        "enumColors": {
          "opened": "yellow",
          "closed": "red",
          "merged": "green",
          "locked": "blue"
        }
      },
      "createdAt": {
        "title": "Create At",
        "type": "string",
        "format": "date-time"
      },
      "updatedAt": {
        "title": "Updated At",
        "type": "string",
        "format": "date-time"
      },
      "description": {
        "title": "Description",
        "type": "string",
        "format": "markdown"
      },
      "link": {
        "title": "Link",
        "format": "url",
        "type": "string"
      }
    }
  }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: mergeRequest
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id | tostring
          title: .title
          blueprint: '"mergeRequest"'
          properties:
            creator: .author.name
            status: .build_status
            stage: .build_stage
            createdAt: .created_at
            startedAt: .started_at
            finishedAt: .finished_at
            description: .description
            link: .web_url
```
</details>

### Job 

The mapping should refer to on of the jobs from the example response: [Gitlab documentation](https://docs.gitlab.com/ee/api/jobs.html#list-project-jobs)

<details>
<summary>blueprint.json</summary>

```json
{
  "identifier": "job",
  "title": "Job",
  "icon": "GitLab",
  "schema": {
    "properties": {
      "createdAt": {
        "title": "Created At",
        "type": "string",
        "format": "date-time"
      },
      "startedAt": {
        "title": "Started At",
        "type": "string",
        "format": "date-time"
      },
      "finishedAt": {
        "title": "Finished At",
        "type": "string",
        "format": "date-time"
      },
      "creator": {
        "title": "Creator",
        "type": "string"
      },
      "stage": {
        "title": "Stage",
        "type": "string"
      },
      "status": {
        "title": "Status",
        "type": "string",
        "enum": [
          "failed",
          "warning",
          "pending",
          "running",
          "manual",
          "scheduled",
          "canceled",
          "success",
          "skipped",
          "created"
        ],
        "enumColors": {
          "failed": "red",
          "warning": "red",
          "pending": "yellow",
          "running": "yellow",
          "manual": "blue",
          "scheduled": "blue",
          "canceled": "red",
          "success": "green",
          "skipped": "red",
          "created": "yellow"
        }
      }
    }
  }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: job
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id | tostring
          title: .name
          blueprint: '"job"'
          properties:
            createdAt: .created_at
            startedAt: .started_at
            finishedAt: .finished_at
            creator: .user.name
            stage: .stage
            status: .state
            link: .web_url
```
</details>

### Pipeline 

The mapping should refer to on of the pipelines from the example response: [Gitlab documentation](https://docs.gitlab.com/ee/api/pipelines.html#list-project-pipelines)

<details>
<summary>blueprint.json</summary>

```json
{
  "identifier": "pipeline",
  "title": "Pipeline",
  "icon": "GitLab",
  "schema": {
    "properties": {
      "createdAt": {
        "title": "Created At",
        "type": "string",
        "format": "date-time"
      },
      "updatedAt": {
        "title": "Updated At",
        "type": "string",
        "format": "date-time"
      },
      "status": {
        "title": "Status",
        "type": "string",
        "enum": [
          "created",
          "waiting_for_resource",
          "preparing",
          "pending",
          "running",
          "success",
          "failed",
          "canceled",
          "skipped",
          "manual",
          "scheduled"
        ],
        "enumColors": {
          "created": "yellow",
          "waiting_for_resource": "yellow",
          "preparing": "yellow",
          "pending": "yellow",
          "running": "yellow",
          "success": "green",
          "failed": "red",
          "canceled": "red",
          "skipped": "red",
          "manual": "blue",
          "scheduled": "blue"
        }
      },
      "stages": {
        "title": "Stages",
        "type": "array",
        "items": {
          "type": "string"
        }
      },
      "link": {
        "title": "Link",
        "type": "string",
        "format": "url"
      }
    }
  }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: pipeline
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id | tostring
          title: .name
          blueprint: '"pipeline"'
          properties:
            createdAt: .created_at
            updatedAt: .updated_at
            status: .status
            link: .web_url
```
</details>


## Installation

```sh
make install
```

## Runnning Localhost
```sh
make run
```
or
```sh
ocean sail
```

## Running Tests

`make test`

## Access Swagger Documentation

> <http://localhost:8080/docs>

## Access Redoc Documentation

> <http://localhost:8080/redoc>


## Folder Structure
The gitlab integration suggested folder structure is as follows:

```
gitlab/
├─ gitlab_integration/      # The integration logic
│  ├─ core/                 # The core logic of the integration
│  ├─ events/               # All the event listeners to the different types of objects in gitlab
│  ├─ ocean.py              # All the ocean implementations with all the @ocean.on_resync implementations
│  ├─ custom_integration.py # Custom implementation of the port integration with git related logic
│  ├─ bootstrap.py          # The bootstrap file that will be used to start the integration and install all the webhooks
│  └─ ...
├─ main.py                  # The main exports the custom Ocean logic to the ocean sail command
└─ ...
```
