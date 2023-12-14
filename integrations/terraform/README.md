# Terraform

Our Terraform integration allows you to import `workspaces` and `runs` from your Terraform Cloud account into Port, according to your mapping and definition.

The Terraform Integration for Port enables seamless import and synchronization of `workspaces` and `runs` from your Terraform infrastructure management into Port. This integration allows you to effectively monitor and manage your Terraform workspaces and runs within the Port platform.

A `Workspace` represents a workspace in Terraform. A workspace is a logical environment where Terraform manages infrastructure, such as a set of cloud resources.

A `Run` represents an instance of Terraform operations (plan, apply, or destroy) executed within a workspace. Each run holds information about the operation status, duration, and other relevant metadata.

## Common use cases

- Synchronization of Infrastructure Management: Automatically synchronize workspace and run data from Terraform into Port for centralized tracking and management.
- Monitoring Run Statuses: Keep track of run outcomes (success, failure, etc.) and durations, providing insights into the health and performance of your infrastructure management processes.

## Prerequisites

<Prerequisites />

## Installation

Choose one of the following installation methods:

<Tabs groupId="installation-methods" queryString="installation-methods">

<TabItem value="real-time-always-on" label="Real Time & Always On" default>

Using this installation option means that the integration will be able to update Port in real time using webhooks.

This table summarizes the available parameters for the installation.
Set them as you wish in the script below, then copy it and run it in your terminal:

| Parameter                               | Description                                                                                                   | Required |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------- | -------- |
| `port.clientId`                         | Your port client id                                                                                           | ✅       |
| `port.clientSecret`                     | Your port client secret                                                                                       | ✅       |
| `port.baseUrl`                          | Your port base url, relevant only if not using the default port app                                           | ❌       |
| `integration.identifier`                | Change the identifier to describe your integration                                                            | ✅       |
| `integration.type`                      | The integration type                                                                                          | ✅       |
| `integration.eventListener.type`        | The event listener type                                                                                       | ✅       |
| `integration.config.terraformToken`     | The Terraform API token                                                                                       | ✅       |
| `integration.config.terraformHost`      | The Terraform host, e.g., https://app.terraform.io"io                                                            | ✅       |
|`integration.config.terraformOrganization`| The Terraform Organization ID |  ✅  |
| `scheduledResyncInterval`               | The number of minutes between each resync                                                                     | ❌       |
| `initializePortResources`               | Default true, When set to true the integration will create default blueprints and the port App config Mapping | ❌       |

<br/>

```bash showLineNumbers
helm repo add --force-update port-labs https://port-labs.github.io/helm-charts
helm upgrade --install terraform port-labs/port-ocean \
	--set port.clientId="PORT_CLIENT_ID"  \
	--set port.clientSecret="PORT_CLIENT_SECRET"  \
	--set port.baseUrl="https://api.getport.io"  \
	--set initializePortResources=true  \
	--set integration.identifier="terraform"  \
	--set integration.type="terraform"  \
	--set integration.eventListener.type="POLLING"  \
	--set integration.config.terraformHost="https://app.terraform.io"  \
	--set integration.secrets.terraformToken="string" \
    --set integration.secrets.terraformOrganization="string"
```

</TabItem>

</TabItem>

<TabItem value="one-time" label="Scheduled">
 <Tabs groupId="cicd-method" queryString="cicd-method">
  <TabItem value="github" label="GitHub">
This workflow will run the Terraform integration once and then exit, this is useful for **scheduled** ingestion of data.

:::warning
If you want the integration to update Port in real time you should use the [Real Time & Always On](?installation-methods=real-time-always-on#installation) installation option
:::

Make sure to configure the following [Github Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions):

| Parameter                                         | Description                                                                                                        | Required |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------- |
| `OCEAN__INTEGRATION__CONFIG__TERRAFORM_TOKEN`       | The Terraform API token                                                                                               | ✅       |
| `OCEAN__INTEGRATION__CONFIG__TERRAFORM_HOST`        | The Terraform host. For example https://app.terraform.io"io                                                                     | ✅       |
| `OCEAN__INTEGRATION__CONFIG__TERRAFORM_ORGANIZATION`    | The Terraform username                                                                                       | ✅       |
| `OCEAN__INITIALIZE_PORT_RESOURCES`                | Default true, When set to false the integration will not create default blueprints and the port App config Mapping | ❌       |
| `OCEAN__INTEGRATION__IDENTIFIER`                  | Change the identifier to describe your integration, if not set will use the default one                            | ❌       |
| `OCEAN__PORT__CLIENT_ID`                          | Your port client id                                                                                                | ✅       |
| `OCEAN__PORT__CLIENT_SECRET`                      | Your port client secret                                                                                            | ✅       |
| `OCEAN__PORT__BASE_URL`                           | Your port base url, relevant only if not using the default port app                                                | ❌       |

<br/>

Here is an example for `terraform-integration.yml` workflow file:

```yaml showLineNumbers
name: Terraform Exporter Workflow


on:
  workflow_dispatch:

jobs:
  run-integration:
    runs-on: ubuntu-latest

    steps:
      - name: Run Terraform Integration
        run: |
          # Set Docker image and run the container
          integration_type="terraform"
          version="latest"

          image_name="ghcr.io/port-labs/port-ocean-$integration_type:$version"

          docker run -i --rm --platform=linux/amd64 \
          -e OCEAN__EVENT_LISTENER='{"type":"ONCE"}' \
          -e OCEAN__INITIALIZE_PORT_RESOURCES=true \
          -e OCEAN__INTEGRATION__CONFIG__TERRAFORM_TOKEN=${{ secrets.OCEAN__INTEGRATION__CONFIG__TERRAFORM_TOKEN }} \
          -e OCEAN__INTEGRATION__CONFIG__TERRAFORM_HOST=${{ secrets.OCEAN__INTEGRATION__CONFIG__TERRAFORM_HOST }} \
          -e OCEAN__INTEGRATION__CONFIG__TERRAFORM_ORGANIZATION=${{ secrets.OCEAN__INTEGRATION__CONFIG__TERRAFORM_ORGANIZATION }} \
          -e OCEAN__PORT__CLIENT_ID=${{ secrets.OCEAN__PORT__CLIENT_ID }} \
          -e OCEAN__PORT__CLIENT_SECRET=${{ secrets.OCEAN__PORT__CLIENT_SECRET }} \
          $image_name
```

  </TabItem>
  <TabItem value="terraform" label="Terraform">
This pipeline will run the Terraform integration once and then exit, this is useful for **scheduled** ingestion of data.

:::tip
Your Jenkins agent should be able to run docker commands.
:::
:::warning
If you want the integration to update Port in real time using webhooks you should use the [Real Time & Always On](?installation-methods=real-time-always-on#installation) installation option.
:::

Make sure to configure the following [Terraf Credentials](https://www.jenkins.io/doc/book/using/using-credentials/) of `Secret Text` type:

| Parameter                                         | Description                                                                                                                                                      | Required |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `OCEAN__INTEGRATION__CONFIG__TERRAFORM_TOKEN`       | The Terraform API token                                                                                                                                             | ✅       |
| `OCEAN__INTEGRATION__CONFIG__TERRAFORM_HOST`        | The Terraform host. For example "https://app.terraform.io"                                                                                                                   | ✅       |
| `OCEAN__INTEGRATION__CONFIG__TERRAFORM_ORGANIZATION`| The Terraform username                                                                                                                                     | ✅       |
| `OCEAN__INITIALIZE_PORT_RESOURCES`                | Default true, When set to false the integration will not create default blueprints and the port App config Mapping                                               | ❌       |
| `OCEAN__INTEGRATION__IDENTIFIER`                  | Change the identifier to describe your integration, if not set will use the default one                                                                          | ❌       |
| `OCEAN__PORT__CLIENT_ID`                          | Your port client id ([How to get the credentials](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/api/#find-your-port-credentials))     | ✅       |
| `OCEAN__PORT__CLIENT_SECRET`                      | Your port client secret ([How to get the credentials](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/api/#find-your-port-credentials)) | ✅       |
| `OCEAN__PORT__BASE_URL`                           | Your port base url, relevant only if not using the default port app                                                                                              | ❌       |

<br/>

Here is an example for `Jenkinsfile` groovy pipeline file:

```yml showLineNumbers
pipeline {
    agent any

    stages {
        stage('Run Terraform Integration') {
            steps {
                script {
                    withCredentials([
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__TERRAFORM_TOKEN', variable: 'OCEAN__INTEGRATION__CONFIG__J_TOKEN'),
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__TERRAFORM_HOST', variable: 'OCEAN__INTEGRATION__CONFIG__TERRAFORM_HOST'),
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__TERRAFORM_ORGANIZATION', variable: 'OCEAN__INTEGRATION__CONFIG___USERNAME'),
                        string(credentialsId: 'OCEAN__PORT__CLIENT_ID', variable: 'OCEAN__PORT__CLIENT_ID'),
                        string(credentialsId: 'OCEAN__PORT__CLIENT_SECRET', variable: 'OCEAN__PORT__CLIENT_SECRET'),
                    ]) {
                        sh('''
                            #Set Docker image and run the container
                            integration_type="terraform"
                            version="latest"
                            image_name="ghcr.io/port-labs/port-ocean-${integration_type}:${version}"
                            docker run -i --rm --platform=linux/amd64 \
                                -e OCEAN__EVENT_LISTENER='{"type":"ONCE"}' \
                                -e OCEAN__INITIALIZE_PORT_RESOURCES=true \
                                -e OCEAN__INTEGRATION__CONFIG__TERRAFORM_TOKEN=$OCEAN__INTEGRATION__CONFIG__TERRAFORM_TOKEN \
                                -e OCEAN__INTEGRATION__CONFIG__TERRAFORM_HOST=$OCEAN__INTEGRATION__CONFIG__TERRAFORM_HOST \
                                -e OCEAN__INTEGRATION__CONFIG__TERRAFORM_ORGANIZATION=$OCEAN__INTEGRATION__CONFIG__TERRAFORM_ORGANIZATION \
                                -e OCEAN__PORT__CLIENT_ID=$OCEAN__PORT__CLIENT_ID \
                                -e OCEAN__PORT__CLIENT_SECRET=$OCEAN__PORT__CLIENT_SECRET \
                                $image_name
                        ''')
                    }
                }
            }
        }
    }
}
```

  </TabItem>
  </Tabs>
</TabItem>

</Tabs>

### Event listener

The integration uses polling to pull the configuration from Port every minute and check it for changes. If there is a change, a resync will occur.

## Ingesting Terraform objects

The Terraform integration uses a YAML configuration to describe the process of loading data into the developer portal.

Here is an example snippet from the config which demonstrates the process for getting `Workspace` from Terraform:

```yaml showLineNumbers
resources:
  - kind: workspace
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .id
          title: .attributes.name
          blueprint: '"terraformWorkspace"'
          properties:
            workspaceName: .attributes.name
            createdAt: .attributes."created-at"
            updatedAt: .attributes."updated-at"
            terraformVersion: .attributes."terraform-version"
            locked: .attributes.locked
            executionMode: .attributes."execution-mode"
            resourceCount: .attributes."resource-count"
            latestChangeAt: .attributes."latest-change-at"

```

The integration makes use of the [JQ JSON processor](https://stedolan.github.io/jq/manual/) to select, modify, concatenate, transform and perform other operations on existing fields and values from Terraform's API events.


### Configuration structure

The integration configuration determines which resources will be queried from Terraform, and which entities and properties will be created in Port.

:::tip Supported resources
The following resources can be used to map data from Terraform, it is possible to reference any field that appears in the API responses linked below for the mapping configuration.

- [`Workspace`](https://www.terraform.io/docs/cloud/api/workspaces.html)
- [`Run`](https://www.terraform.io/docs/cloud/api/runs.html)

:::

- The root key of the integration configuration is the `resources` key:

  ```yaml showLineNumbers
  # highlight-next-line
  resources:
    - kind: workspace
      selector:
      ...
  ```

- The `kind` key is a specifier for a Terraform object:

  ```yaml showLineNumbers
    resources:
      # highlight-next-line
      - kind: run
        selector:
        ...
  ```

- The `port`, `entity` and the `mappings` keys are used to map the Terraform object fields to Port entities. To create multiple mappings of the same kind, you can add another item in the `resources` array;

```yaml showLineNumbers
resources:
  - kind: workspace
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .id
          title: .attributes.name
          blueprint: '"terraformWorkspace"'
          properties:
            workspaceName: .attributes.name
            createdAt: .attributes."created-at"
            updatedAt: .attributes."updated-at"
            terraformVersion: .attributes."terraform-version"
            locked: .attributes.locked
            executionMode: .attributes."execution-mode"
            resourceCount: .attributes."resource-count"
            latestChangeAt: .attributes."latest-change-at"
```

  :::tip Blueprint key
  Note the value of the `blueprint` key - if you want to use a hardcoded string, you need to encapsulate it in 2 sets of quotes, for example use a pair of single-quotes (`'`) and then another pair of double-quotes (`"`)
  :::


### Ingest data into Port

To ingest Terraform objects using the [integration configuration](#configuration-structure), you can follow the steps below:

1. Go to the DevPortal Builder page.
2. Select a blueprint you want to ingest using Terraform.
3. Choose the **Ingest Data** option from the menu.
4. Select Terraform under the IaC category.
5. Add the contents of your [integration configuration](#configuration-structure) to the editor.
6. Click `Resync`.
6. Click `Resync`.

## Examples

Examples of blueprints and the relevant integration configurations:

### Workspace

<details>
<summary>Workspace blueprint</summary>

```json showLineNumbers

    {
        "identifier": "terraformWorkspace",
        "description": "This blueprint represents a workspace in Terraform",
        "title": "Terraform Workspace",
        "icon": "Terraform",
        "schema": {
          "properties": {
            "workspaceName": {
              "type": "string",
              "title": "Workspace Name",
              "description": "The name of the Terraform workspace"
            },
            "createdAt": {
              "type": "string",
              "format": "date-time",
              "title": "Creation Time",
              "description": "The creation timestamp of the workspace"
            },
            "updatedAt": {
              "type": "string",
              "format": "date-time",
              "title": "Last Updated",
              "description": "The last update timestamp of the workspace"
            },
            "terraformVersion": {
              "type": "string",
              "title": "Terraform Version",
              "description": "Version of Terraform used by the workspace"
            },
            "locked": {
              "type": "boolean",
              "title": "Locked Status",
              "description": "Indicates whether the workspace is locked"
            },
            "executionMode": {
              "type": "string",
              "title": "Execution Mode",
              "description": "The execution mode of the workspace"
            },
            "resourceCount": {
              "type": "number",
              "title": "Resource Count",
              "description": "Number of resources managed by the workspace"
            },
            "latestChangeAt": {
              "type": "string",
              "format": "date-time",
              "title": "Latest Change",
              "description": "Timestamp of the latest change in the workspace"
            }
          }
        }
      }
```

</details>

<details>
<summary>Integration configuration</summary>

```yaml showLineNumbers
resources:
  - kind: workspace
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .id
          title: .attributes.name
          blueprint: '"terraformWorkspace"'
          properties:
            workspaceName: .attributes.name
            createdAt: .attributes."created-at"
            updatedAt: .attributes."updated-at"
            terraformVersion: .attributes."terraform-version"
            locked: .attributes.locked
            executionMode: .attributes."execution-mode"
            resourceCount: .attributes."resource-count"
            latestChangeAt: .attributes."latest-change-at"
```

### Build

<details>
<summary>Run blueprint</summary>

```json showLineNumbers

{
  "identifier": "terraformRun",
  "description": "This blueprint represents a run in Terraform",
  "title": "Terraform Run",
  "icon": "Terraform",
  "schema": {
    "properties": {
      "runId": {
        "type": "string",
        "title": "Run ID",
        "description": "The unique identifier of the Terraform run"
      },
      "createdAt": {
        "type": "string",
        "format": "date-time",
        "title": "Creation Time",
        "description": "The creation timestamp of the run"
      },
      "status": {
        "type": "string",
        "title": "Run Status",
        "description": "The current status of the run"
      },
      "hasChanges": {
        "type": "boolean",
        "title": "Has Changes",
        "description": "Indicates whether the run has changes"
      },
      "isDestroy": {
        "type": "boolean",
        "title": "Is Destroy",
        "description": "Indicates whether the run is a destroy operation"
      },
      "message": {
        "type": "string",
        "title": "Run Message",
        "description": "Message associated with the run"
      },
      "terraformVersion": {
        "type": "string",
        "title": "Terraform Version",
        "description": "Version of Terraform used in the run"
      },
      "appliedAt": {
        "type": "string",
        "format": "date-time",
        "title": "Applied Time",
        "description": "Timestamp when the run was applied"
      },
      "plannedAt": {
        "type": "string",
        "format": "date-time",
        "title": "Planned Time",
        "description": "Timestamp when the run was planned"
      },
      "source": {
        "type": "string",
        "title": "Run Source",
        "description": "The source of the run initiation"
      }
    }
  },
  "relations": {
    "terraformWorkspace": {
      "title": "Terraform Workspace",
      "target": "terraformWorkspace",
      "required": true,
      "many": false
    }
  }
}

```


</details>

<details>
<summary>Integration configuration</summary>

```yaml showLineNumbers
  - kind: run
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .id
          title: .attributes.message
          blueprint: '"terraformRun"'
          properties:
            runId: .id
            createdAt: .attributes."created-at"
            status: .attributes.status
            hasChanges: .attributes."has-changes"
            isDestroy: .attributes."is-destroy"
            message: .attributes.message
            terraformVersion: .attributes."terraform-version"
            appliedAt: .attributes."status-timestamps"."applied-at"
            plannedAt: .attributes."status-timestamps"."planned-at"
            source: .attributes.source
          relations: 
            terraformWorkspace: .relationships.workspace.data.id

```

</details>

## Let's Test It

This section includes a sample response data from Terrform. In addition, it includes the entity created from the resync event based on the Ocean configuration provided in the previous section.

### Payload

Here is an example of the payload structure from Terraform:

<details>
<summary> Workspace response data</summary>

```json showLineNumbers

{
      "id":"ws-WWhD18B59v5ndTTP",
      "type":"workspaces",
      "attributes":{
         "allow-destroy-plan":true,
         "auto-apply":false,
         "auto-apply-run-trigger":false,
         "auto-destroy-activity-duration":"None",
         "auto-destroy-at":"None",
         "auto-destroy-status":"None",
         "created-at":"2023-12-11T20:20:07.614Z",
         "environment":"default",
         "locked":false,
         "name":"getting-started",
         "queue-all-runs":false,
         "speculative-enabled":true,
         "structured-run-output-enabled":true,
         "terraform-version":"1.6.5",
         "working-directory":"None",
         "global-remote-state":false,
         "updated-at":"2023-12-12T10:06:46.205Z",
         "resource-count":5,
         "apply-duration-average":4000,
         "plan-duration-average":5000,
         "policy-check-failures":0,
         "run-failures":0,
         "workspace-kpis-runs-count":1,
         "latest-change-at":"2023-12-12T10:06:45.192Z",
         "operations":true,
         "execution-mode":"remote",
         "vcs-repo":"None",
         "vcs-repo-identifier":"None",
         "permissions":{
            "can-update":true,
            "can-destroy":true,
            "can-queue-run":true,
            "can-read-variable":true,
            "can-update-variable":true,
            "can-read-state-versions":true,
            "can-read-state-outputs":true,
            "can-create-state-versions":true,
            "can-queue-apply":true,
            "can-lock":true,
            "can-unlock":true,
            "can-force-unlock":true,
            "can-read-settings":true,
            "can-manage-tags":true,
            "can-manage-run-tasks":true,
            "can-force-delete":true,
            "can-manage-assessments":true,
            "can-manage-ephemeral-workspaces":false,
            "can-read-assessment-results":true,
            "can-queue-destroy":true
         },
         "actions":{
            "is-destroyable":true
         },
         "description":"None",
         "file-triggers-enabled":true,
         "trigger-prefixes":[
            
         ],
         "trigger-patterns":[
            
         ],
         "assessments-enabled":false,
         "last-assessment-result-at":"None",
         "source":"None",
         "source-name":"None",
         "source-url":"None",
         "tag-names":[
            
         ],
         "setting-overwrites":{
            "execution-mode":true,
            "agent-pool":true
         }
      },
      "relationships":{
         "organization":{
            "data":{
               "id":"example-org-162af6",
               "type":"organizations"
            }
         },
         "current-run":{
            "data":{
               "id":"run-28xMcbm8uCzsFoZE",
               "type":"runs"
            },
            "links":{
               "related":"/api/v2/runs/run-28xMcbm8uCzsFoZE"
            }
         },
         "latest-run":{
            "data":{
               "id":"run-28xMcbm8uCzsFoZE",
               "type":"runs"
            },
            "links":{
               "related":"/api/v2/runs/run-28xMcbm8uCzsFoZE"
            }
         },
         "outputs":{
            "data":[
               
            ],
            "links":{
               "related":"/api/v2/workspaces/ws-WWhD18B59v5ndTTP/current-state-version-outputs"
            }
         },
         "remote-state-consumers":{
            "links":{
               "related":"/api/v2/workspaces/ws-WWhD18B59v5ndTTP/relationships/remote-state-consumers"
            }
         },
         "current-state-version":{
            "data":{
               "id":"sv-U6L87Bf6JcZqcXoi",
               "type":"state-versions"
            },
            "links":{
               "related":"/api/v2/workspaces/ws-WWhD18B59v5ndTTP/current-state-version"
            }
         },
         "current-configuration-version":{
            "data":{
               "id":"cv-ompZmuF15X68njap",
               "type":"configuration-versions"
            },
            "links":{
               "related":"/api/v2/configuration-versions/cv-ompZmuF15X68njap"
            }
         },
         "agent-pool":{
            "data":"None"
         },
         "readme":{
            "data":"None"
         },
         "project":{
            "data":{
               "id":"prj-wnLLjhXa3XArrRFR",
               "type":"projects"
            }
         },
         "current-assessment-result":{
            "data":"None"
         },
         "vars":{
            "data":[
               {
                  "id":"var-hWAFtXNz8kLmsLWV",
                  "type":"vars"
               }
            ]
         }
      },
      "links":{
         "self":"/api/v2/organizations/example-org-162af6/workspaces/getting-started",
         "self-html":"/app/example-org-162af6/workspaces/getting-started"
      }
   }

```
</details>

<details>
<summary> Runs response data</summary>


```json showLineNumbers

{
 "data":
     [
        {
      "id":"run-SFSeL9fg6Kibje8L",
      "type":"runs",
      "attributes":{
         "actions":{
            "is-cancelable":false,
            "is-confirmable":false,
            "is-discardable":false,
            "is-force-cancelable":false
         },
         "allow-config-generation":true,
         "allow-empty-apply":false,
         "auto-apply":false,
         "canceled-at":"None",
         "created-at":"2023-12-13T12:12:40.252Z",
         "has-changes":false,
         "is-destroy":false,
         "message":"just checking this out",
         "plan-only":false,
         "refresh":true,
         "refresh-only":false,
         "replace-addrs":[
            
         ],
         "save-plan":false,
         "source":"tfe-ui",
         "status-timestamps":{
            "planned-at":"2023-12-13T12:12:54+00:00",
            "queuing-at":"2023-12-13T12:12:40+00:00",
            "planning-at":"2023-12-13T12:12:49+00:00",
            "plan-queued-at":"2023-12-13T12:12:40+00:00",
            "plan-queueable-at":"2023-12-13T12:12:40+00:00",
            "planned-and-finished-at":"2023-12-13T12:12:54+00:00"
         },
         "status":"planned_and_finished",
         "target-addrs":"None",
         "trigger-reason":"manual",
         "terraform-version":"1.6.5",
         "permissions":{
            "can-apply":true,
            "can-cancel":true,
            "can-comment":true,
            "can-discard":true,
            "can-force-execute":true,
            "can-force-cancel":true,
            "can-override-policy-check":true
         },
         "variables":[
            
         ]
      },
      "relationships":{
         "workspace":{
            "data":{
               "id":"ws-WWhD18B59v5ndTTP",
               "type":"workspaces"
            }
         },
         "apply":{
            "data":{
               "id":"apply-ToVWRgBe4mmGwTf7",
               "type":"applies"
            },
            "links":{
               "related":"/api/v2/runs/run-SFSeL9fg6Kibje8L/apply"
            }
         },
         "configuration-version":{
            "data":{
               "id":"cv-ompZmuF15X68njap",
               "type":"configuration-versions"
            },
            "links":{
               "related":"/api/v2/runs/run-SFSeL9fg6Kibje8L/configuration-version"
            }
         },
         "created-by":{
            "data":{
               "id":"user-Vg6uYxyhrQSHNrKU",
               "type":"users"
            },
            "links":{
               "related":"/api/v2/runs/run-SFSeL9fg6Kibje8L/created-by"
            }
         },
         "plan":{
            "data":{
               "id":"plan-3rXS4BMT8TEkdchh",
               "type":"plans"
            },
            "links":{
               "related":"/api/v2/runs/run-SFSeL9fg6Kibje8L/plan"
            }
         },
         "run-events":{
            "data":[
               {
                  "id":"re-WgvYmckRJjafwU5R",
                  "type":"run-events"
               },
               {
                  "id":"re-46PfZixftNeifEG9",
                  "type":"run-events"
               },
               {
                  "id":"re-LCCwB2pQNPrGnveF",
                  "type":"run-events"
               },
               {
                  "id":"re-YoviSEov4cscqfi7",
                  "type":"run-events"
               }
            ],
            "links":{
               "related":"/api/v2/runs/run-SFSeL9fg6Kibje8L/run-events"
            }
         },
         "task-stages":{
            "data":[
               
            ],
            "links":{
               "related":"/api/v2/runs/run-SFSeL9fg6Kibje8L/task-stages"
            }
         },
         "policy-checks":{
            "data":[
               
            ],
            "links":{
               "related":"/api/v2/runs/run-SFSeL9fg6Kibje8L/policy-checks"
            }
         },
         "comments":{
            "data":[
               
            ],
            "links":{
               "related":"/api/v2/runs/run-SFSeL9fg6Kibje8L/comments"
            }
         }
      },
      "links":{
         "self":"/api/v2/runs/run-SFSeL9fg6Kibje8L"
      }
   }
   ]
}


```


### Mapping Result

The combination of the sample payload and the Ocean configuration generates the following Port entity:

<details>
<summary> workspace entity in Port</summary>

```json showLineNumbers
{
  "identifier": "ws-WWhD18B59v5ndTTP",
  "title": "getting-started",
  "team": [],
  "properties": {
    "workspaceName": "getting-started",
    "createdAt": "2023-12-11T20:20:07.614Z",
    "updatedAt": "2023-12-14T17:49:21.650Z",
    "terraformVersion": "1.6.5",
    "locked": false,
    "executionMode": "remote",
    "resourceCount": 5,
    "latestChangeAt": "2023-12-12T10:06:45.192Z"
  },
  "relations": {},
  "icon": "Terraform"
}

```

</details>



### Mapping Result

The combination of the sample payload and the Ocean configuration generates the following Port entity:

<details>
<summary> Run entity in Port</summary>

```json showLineNumbers

{
    "identifier": "run-SFSeL9fg6Kibje8L",
    "title": "just checking this out",
    "blueprint": "terraformRun",
    "properties": {
      "runId": "run-SFSeL9fg6Kibje8L",
      "createdAt": "2021-08-16T21:50:58.726Z",
      "status": "planned_and_finished",
      "hasChanges": false,
      "isDestroy": false,
      "message": "just checking this out",
      "terraformVersion": "0.11.1",
      "appliedAt": null,
      "plannedAt": "2023-12-13T12:12:54+00:00",
      "source": "tfe-api"
    },
    "relations": {},
  }


</details>



### Mapping Result

The combination of the sample payload and the Ocean configuration generates the following Port entity: