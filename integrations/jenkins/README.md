import Tabs from "@theme/Tabs"
import TabItem from "@theme/TabItem"
import Prerequisites from "../templates/\_ocean_helm_prerequisites_block.mdx"
import DockerParameters from "./\_jenkins-docker-parameters.mdx"

# Jenkins

Our Jenkins integration allows you to import `job` and `build` objects from your Jenkins instance into Port, according to your mapping and definition.

### Common use cases
Our Jenkins integration makes it easy to fill the software catalog with data directly from your Jenkins server, for example:

- Map all of the jobs and builds in your Jenkins server;
- Watch for Jenkins object changes (create/update/delete) in real-time, and automatically apply the changes to your entities in Port

## Prerequisites

<Prerequisites />

#### Installation

Choose one of the following installation methods:

<Tabs groupId="installation-methods" queryString="installation-methods">

<TabItem value="real-time-always-on" label="Real Time & Always On" default>

Using this installation option means that the integration will be able to update Port in real time.

This table summarizes the available parameters for the installation.
Set them as you wish in the script below, then copy it and run it in your terminal:

| Parameter                         | Description                                                                                                   | Required |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------- | -------- |
| `port.clientId`                   | Your port client id                                                                                           | ✅       |
| `port.clientSecret`               | Your port client secret                                                                                       | ✅       |
| `port.baseUrl`                    | Your port base url, relevant only if not using the default port app                                           | ❌       |
| `integration.identifier`          | Change the identifier to describe your integration                                                            | ✅       |
| `integration.type`                | The integration type                                                                                          | ✅       |
| `integration.eventListener.type`  | The event listener type                                                                                       | ✅       |
| `integration.config.jenkinsHost`  | The Jenkins server URL                                                                                        | ✅       |
| `integration.secrets.jenkinsUser`  | The Jenkins server username                                                                                        | ✅       |
| `integration.secrets.jenkinsPassword`  | The Jenkins server password                                                                                        | ✅       |
| `scheduledResyncInterval`         | The number of minutes between each resync                                                                     | ❌       |
| `initializePortResources`         | Default true, When set to true the integration will create default blueprints and the port App config Mapping | ❌       |

<br/>

```bash showLineNumbers
helm repo add --force-update port-labs https://port-labs.github.io/helm-charts
helm upgrade --install my-jenkins-integration port-labs/port-ocean \
  --set port.clientId="CLIENT_ID"  \
  --set port.clientSecret="CLIENT_SECRET"  \
  --set initializePortResources=true  \
  --set scheduledResyncInterval=60 \
  --set integration.identifier="my-jenkins-integration"  \
  --set integration.type="Jenkins"  \
  --set integration.eventListener.type="POLLING"  \
  --set integration.config.JenkinsHost="https://JenkinsInstance:8080" \
  --set integration.secrets.jenkinsUser="string"  \
  --set integration.secrets.jenkinsPassword="string"
```

</TabItem>

<TabItem value="one-time" label="One Time">
  <Tabs groupId="cicd-method" queryString="cicd-method">
  <TabItem value="github" label="GitHub">
This workflow will run the Jenkins integration once and then exit, this is useful for **one time** ingestion of data.

:::warning
If you want the integration to update Port in real time you should use the [Real Time & Always On](?installation-methods=real-time-always-on#installation) installation option
:::

Make sure to configure the following [Github Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions):

<DockerParameters />

<br/>

Here is an example for `jenkins-integration.yml` workflow file:

```yaml showLineNumbers
name: Jenkins Exporter Workflow

# This workflow responsible for running Jenkins exporter.

on:
  workflow_dispatch:

jobs:
  run-integration:
    runs-on: ubuntu-latest

    steps:
      - name: Run Jenkins Integration
        run: |
          # Set Docker image and run the container
          integration_type="jenkins"
          version="latest"

          image_name="ghcr.io/port-labs/port-ocean-$integration_type:$version"

          docker run -i --rm --platform=linux/amd64 \
          -e OCEAN__EVENT_LISTENER='{"type":"ONCE"}' \
          -e OCEAN__INITIALIZE_PORT_RESOURCES=true \
          -e OCEAN__INTEGRATION__CONFIG__JENKINS_HOST=${{ secrets.OCEAN__INTEGRATION__CONFIG__JENKINS_HOST }} \
          -e OCEAN__INTEGRATION__CONFIG__JENKINS_USER=${{ secrets.OCEAN__INTEGRATION__CONFIG__JENKINS_USER }} \
          -e OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD=${{ secrets.OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD }} \
          -e OCEAN__PORT__CLIENT_ID=${{ secrets.OCEAN__PORT__CLIENT_ID }} \
          -e OCEAN__PORT__CLIENT_SECRET=${{ secrets.OCEAN__PORT__CLIENT_SECRET }} \
          $image_name
```

  </TabItem>
  <TabItem value="jenkins" label="Jenkins">
This pipeline will run the Jenkins integration once and then exit, this is useful for **one time** ingestion of data.

:::tip
Your Jenkins agent should be able to run docker commands.
:::
:::warning
If you want the integration to update Port in real time using webhooks you should use
the [Real Time & Always On](?installation-methods=real-time-always-on#installation) installation option.
:::

Make sure to configure the following [Jenkins Credentials](https://www.jenkins.io/doc/book/using/using-credentials/)
of `Secret Text` type:

<DockerParameters />

<br/>

Here is an example for `Jenkinsfile` groovy pipeline file:

```text showLineNumbers
pipeline {
    agent any

    stages {
        stage('Run Jenkins Integration') {
            steps {
                script {
                    withCredentials([
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_HOST', variable: 'OCEAN__INTEGRATION__CONFIG__JENKINS_HOST'),
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_USER', variable: 'OCEAN__INTEGRATION__CONFIG__JENKINS_USER'),
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD', variable: 'OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD'),
                        string(credentialsId: 'OCEAN__PORT__CLIENT_ID', variable: 'OCEAN__PORT__CLIENT_ID'),
                        string(credentialsId: 'OCEAN__PORT__CLIENT_SECRET', variable: 'OCEAN__PORT__CLIENT_SECRET'),
                    ]) {
                        sh('''
                            #Set Docker image and run the container
                            integration_type="jenkins"
                            version="latest"
                            image_name="ghcr.io/port-labs/port-ocean-${integration_type}:${version}"
                            docker run -i --rm --platform=linux/amd64 \
                                -e OCEAN__EVENT_LISTENER='{"type":"ONCE"}' \
                                -e OCEAN__INITIALIZE_PORT_RESOURCES=true \
                                -e OCEAN__INTEGRATION__CONFIG__JENKINS_HOST=$OCEAN__INTEGRATION__CONFIG__JENKINS_HOST \
                                -e OCEAN__INTEGRATION__CONFIG__JENKINS_USER=$OCEAN__INTEGRATION__CONFIG__JENKINS_USER \
                                -e OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD=$OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD \
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

## Ingesting Jenkins objects

The Jenkins integration uses a YAML configuration to describe the process of loading data into the developer portal.

Here is an example snippet from the config which demonstrates the process for getting job data from Jenkins:

```yaml showLineNumbers
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
  - kind: job
    selector:
      query:  "true"
    port:
      entity:
        mappings:
          identifier: 'if .url | contains("://") then (.url | split("://")[1] | sub("^.*?/"; "")) else .url end | sub("%20"; "-"; "g") | sub("/"; "-"; "g") | .[:-1]'
          title: .displayName
          blueprint: '"job"'
          properties:
            jobName: .fullName
            url: '.url | if test("://") then sub("^[^/]+//[^/]+"; "") else . end'
            jobStatus: '.color as $input | if $input == "notbuilt" then "created" else "updated" end'
            timestamp: .time
```

The integration makes use of the [JQ JSON processor](https://stedolan.github.io/jq/manual/) to select, modify, concatenate, transform and perform other operations on existing fields and values from Jenkins's API events.

### Configuration structure

The integration configuration determines which resources will be queried from Jenkins, and which entities and properties will be created in Port.

:::tip Supported resources
The following resources can be used to map data from Jenkins, it is possible to reference any field that appears in the API responses linked below for the mapping configuration.

- [`job`](https://www.jenkins.io/doc/pipeline/tour/hello-world/)
- [`build`](https://www.jenkins.io/doc/tutorials/#tools)

:::

:::note
You will be able to see realtime `build` data after you have successfully configured the web hook on your Jenkins instance according to this [documentation](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/ci-cd/jenkins)
:::

- The root key of the integration configuration is the `resources` key:

  ```yaml showLineNumbers
  # highlight-next-line
  resources:
    - kind: job
      selector:
      ...
  ```

- The `kind` key is a specifier for an Jenkins object:

  ```yaml showLineNumbers
    resources:
      # highlight-next-line
      - kind: job
        selector:
        ...
  ```

- The `selector` and the `query` keys allow you to filter which objects of the specified `kind` will be ingested into your software catalog:

  ```yaml showLineNumbers
  resources:
    - kind: job
      # highlight-start
      selector:
        query: "true" # JQ boolean expression. If evaluated to false - this object will be skipped.
      # highlight-end
      port:
  ```


- The `port`, `entity` and the `mappings` keys are used to map the Jenkins object fields to Port entities. To create multiple mappings of the same kind, you can add another item in the `resources` array;

  ```yaml showLineNumbers
  resources:
    - kind: job
      selector:
        query: "true"
      port:
        # highlight-start
        entity:
          mappings: # Mappings between one Jenkins object to a Port entity. Each value is a JQ query.
            identifier: 'if .url | contains("://") then (.url | split("://")[1] | sub("^.*?/"; "")) else .url end | sub("%20"; "-"; "g") | sub("/"; "-"; "g") | .[:-1]'
            title: .displayName
            blueprint: '"job"'
            properties:
               jobName: .fullName
               url: '.url | if test("://") then sub("^[^/]+//[^/]+"; "") else . end'
               jobStatus: '.color as $input | if $input == "notbuilt" then "created" else "updated" end'
               timestamp: .time
        # highlight-end
    - kind: job # In this instance cost is mapped again with a different filter
      selector:
        query:  .type | startswith("item")
      port:
        entity:
          mappings: ...
  ```

  :::tip Blueprint key
  Note the value of the `blueprint` key - if you want to use a hardcoded string, you need to encapsulate it in 2 sets of quotes, for example use a pair of single-quotes (`'`) and then another pair of double-quotes (`"`)
  :::

### Ingest data into Port

To ingest Jenkins objects using the [integration configuration](#configuration-structure), you can follow the steps below:

1. Go to the DevPortal Builder page.
2. Select a blueprint you want to ingest using Jenkins.
3. Choose the **Ingest Data** option from the menu.
4. Select Jenkins under the Cloud cost providers category.
5. Modify the [configuration](#configuration-structure) according to your needs.
6. Click `Resync`.

## Examples

Examples of blueprints and the relevant integration configurations:

### Job

<details>
<summary>Job blueprint</summary>

```json showLineNumbers
{
    "identifier": "job",
    "description": "This blueprint represents a job event from Jenkins",
    "title": "Jenkins Job",
    "icon": "Jenkins",
    "schema": {
        "properties": {
            "jobName": {
                "type": "string",
                "title": "Project Name"
            },
            "jobStatus": {
                "type": "string",
                "title": "Job Status",
                "enum": ["created", "updated", "deleted"],
                "enumColors": {
                    "created": "green",
                    "updated": "yellow",
                    "deleted": "red"
                }
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "title": "Timestamp",
                "description": "Last updated timestamp of the job"
            },
            "url": {
                "type": "string",
                "title": "Project URL"
            },
            "jobFullUrl": {
                "type": "string",
                "title": "Job Full URL",
                "format": "url"
            }
        },
        "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {}
}
```

</details>

<details>
<summary>Integration configuration</summary>

```yaml showLineNumbers
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
  - kind: job
    selector:
      query:  "true"
    port:
      entity:
        mappings:
          identifier: 'if .url | contains("://") then (.url | split("://")[1] | sub("^.*?/"; "")) else .url end | sub("%20"; "-"; "g") | sub("/"; "-"; "g") | .[:-1]'
          title: .displayName
          blueprint: '"job"'
          properties:
            jobName: .fullName
            url: '.url | if test("://") then sub("^[^/]+//[^/]+"; "") else . end'
            jobStatus: '.color as $input | if $input == "notbuilt" then "created" else "updated" end'
            timestamp: .time
```

</details>

### Build

<details>
<summary> Build blueprint</summary>

```json showlineNumbers
{
    "identifier": "build",
    "description": "This blueprint represents a build event from Jenkins",
    "title": "Jenkins Build",
    "icon": "Jenkins",
    "schema": {
        "properties": {
            "buildStatus": {
                "type": "string",
                "title": "Build Status",
                "enum": ["SUCCESS", "FAILURE", "UNSTABLE"],
                "enumColors": {
                    "SUCCESS": "green",
                    "FAILURE": "red",
                    "UNSTABLE": "yellow"
                }
            },
            "buildUrl": {
                "type": "string",
                "title": "Build URL",
                "description": "URL to the build"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "title": "Timestamp",
                "description": "Last updated timestamp of the build"
            },
            "buildDuration": {
                "type": "number",
                "title": "Build Duration",
                "description": "Duration of the build"
            }
        },
        "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
        "job": {
            "title": "Jenkins Job",
            "target": "job",
            "required": false,
            "many": false
        }
    }
}
```

</details>

<details>
<summary>Integration configuration</summary>

```yaml showLineNumbers
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
  - kind: build
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: '.fullDisplayName | sub(" "; "-"; "g") | sub("#"; ""; "g")'
          title: .displayName
          blueprint: '"build"'
          properties:
            buildStatus: .result
            buildUrl: '.url | if test("://") then sub("^[^/]+//[^/]+"; "") else . end'
            buildDuration: .duration
            timestamp: '.timestamp as $input | if $input | type == "number" then ($input / 1000 | todate) else $input end'
          relations:
            job: '.url as $input | if $input | contains("://") then ($input | split("://")[1] | sub("^.*?/"; "")) else $input end | tostring | sub("%20"; "-"; "g") | sub("/"; "-"; "g") | .[:-1] | sub("-[0-9]+$"; "")'
```

</details>

## Let's Test It

This section includes a sample response data from Jenkins. In addition, it includes the entity created from the resync event based on the Ocean configuration provided in the previous section.

### Payload

Here is an example of the payload structure from Jenkins:

<details>
<summary> Jobs response data</summary>

```json showLineNumbers
{
   "_class":"org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject",
   "description":"The hauora app",
   "displayName":"Hauora App",
   "fullDisplayName":"Hauora App",
   "fullName":"Haoura",
   "name":"Haoura",
   "url":"http://localhost:8080/job/Haoura/"
}
```

</details>

### Mapping Result

The combination of the sample payload and the Ocean configuration generates the following Port entity:

<details>
<summary> Job entity in Port</summary>

```json showLineNumbers
{
  "identifier": "job-Hauora",
  "title": "Hauora",
  "icon": null,
  "blueprint": "job",
  "team": [],
  "properties": {
    "jobName": "Hauora",
    "jobStatus": null,
    "timestamp": null,
    "url": "/job/Hauora/",
    "jobFullUrl": null
  },
  "relations": {},
  "createdAt": "2023-11-30T18:20:19.438Z",
  "createdBy": "9jFVohNK1Zrz7zDml3xvG8hu38wiM5s0",
  "updatedAt": "2023-11-30T18:20:19.438Z",
  "updatedBy": "9jFVohNK1Zrz7zDml3xvG8hu38wiM5s0"
}
```

</details>