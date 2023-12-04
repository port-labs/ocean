import Tabs from "@theme/Tabs"
import TabItem from "@theme/TabItem"
import Prerequisites from "../templates/\_ocean_helm_prerequisites_block.mdx"

# Jenkins

Our Jenkins integration allows you to import `jobs` and `builds` from your Jenkins cloud account into Port, according to your mapping and definition.

The Jenkins Integration for Port enables seamless import and synchronization of `jobs` and  `buids` from your Jenkins CI/CD server into Port. This integration allows you to effectively monitor and manage your Jenkins jobs and builds within the Port platform.

A `Job` represents a job in Jenkins. A job can be any runnable task defined in Jenkins, such as a build project or a pipeline..

A `Build` represents a build executed as part of a Jenkins job. Each build holds information about the execution status, duration, and other relevant metadata.

## Common use cases

- Map your monitored projects and issues into Port.
- Synchronization of CI/CD Pipelines : Automatically synchronize and build data from Jenkins into Port for centralized tracking and management.
- Monitoring Build Statuses : Keep track of build outcomes (Success, Failure, Unstable) and durations, providing insights into the health and performance of your software development processes.

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
| `integration.secrets.jenkinsToken`      | The Jenkins API token token                                                                                   | ✅       |
| `integration.config.jenkinsHost`        | The Jenkins host. For example https://jenkins.io                                                              | ✅       |
| `integration.config.jenkinsOrganization`| The Jenkins organization slug                                                                                 | ✅       |
| `scheduledResyncInterval`               | The number of minutes between each resync                                                                     | ❌       |
| `initializePortResources`               | Default true, When set to true the integration will create default blueprints and the port App config Mapping | ❌       |

<br/>

```bash showLineNumbers
helm repo add --force-update port-labs https://port-labs.github.io/helm-charts
helm upgrade --install jenkins port-labs/port-ocean \
	--set port.clientId="PORT_CLIENT_ID"  \
	--set port.clientSecret="PORT_CLIENT_SECRET"  \
	--set port.baseUrl="https://api.getport.io"  \
	--set initializePortResources=true  \
	--set integration.identifier="jenkins"  \
	--set integration.type="jenkins"  \
	--set integration.eventListener.type="POLLING"  \
	--set integration.config.jenkinsHost="https://jenkins.io"  \
	--set integration.secrets.jenkinsToken="string"  \
	--set integration.config.jenkinsOrganization="string"
```

</TabItem>

<TabItem value="one-time" label="Scheduled">
 <Tabs groupId="cicd-method" queryString="cicd-method">
  <TabItem value="github" label="GitHub">
This workflow will run the Jenkins integration once and then exit, this is useful for **scheduled** ingestion of data.

:::warning
If you want the integration to update Port in real time you should use the [Real Time & Always On](?installation-methods=real-time-always-on#installation) installation option
:::

Make sure to configure the following [Github Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions):

| Parameter                                         | Description                                                                                                        | Required |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------- |
| `OCEAN__INTEGRATION__CONFIG__JENKINS_TOKEN`       | The Jenkins API token                                                                                               | ✅       |
| `OCEAN__INTEGRATION__CONFIG__JENKINS_HOST`        | The Jenkins host. For example https://jenkins.io                                                                     | ✅       |
| `OCEAN__INTEGRATION__CONFIG__JENKINS_ORGANIZATION`| The Jenkins organization slug                                                                                       | ✅       |
| `OCEAN__INITIALIZE_PORT_RESOURCES`                | Default true, When set to false the integration will not create default blueprints and the port App config Mapping | ❌       |
| `OCEAN__INTEGRATION__IDENTIFIER`                  | Change the identifier to describe your integration, if not set will use the default one                            | ❌       |
| `OCEAN__PORT__CLIENT_ID`                          | Your port client id                                                                                                | ✅       |
| `OCEAN__PORT__CLIENT_SECRET`                      | Your port client secret                                                                                            | ✅       |
| `OCEAN__PORT__BASE_URL`                           | Your port base url, relevant only if not using the default port app                                                | ❌       |

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
          -e OCEAN__INTEGRATION__CONFIG__JENKINS_TOKEN=${{ secrets.OCEAN__INTEGRATION__CONFIG__JENKINS_TOKEN }} \
          -e OCEAN__INTEGRATION__CONFIG__JENKINS_HOST=${{ secrets.OCEAN__INTEGRATION__CONFIG__JENKINS_HOST }} \
          -e OCEAN__INTEGRATION__CONFIG__JENKINS_ORGANIZATION=${{ secrets.OCEAN__INTEGRATION__CONFIG__JENKINS_ORGANIZATION }} \
          -e OCEAN__PORT__CLIENT_ID=${{ secrets.OCEAN__PORT__CLIENT_ID }} \
          -e OCEAN__PORT__CLIENT_SECRET=${{ secrets.OCEAN__PORT__CLIENT_SECRET }} \
          $image_name
```

  </TabItem>
  <TabItem value="jenkins" label="Jenkins">
This pipeline will run the Jenkins integration once and then exit, this is useful for **scheduled** ingestion of data.

:::tip
Your Jenkins agent should be able to run docker commands.
:::
:::warning
If you want the integration to update Port in real time using webhooks you should use the [Real Time & Always On](?installation-methods=real-time-always-on#installation) installation option.
:::

Make sure to configure the following [Jenkins Credentials](https://www.jenkins.io/doc/book/using/using-credentials/) of `Secret Text` type:

| Parameter                                         | Description                                                                                                                                                      | Required |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `OCEAN__INTEGRATION__CONFIG__JENKINS_TOKEN`       | The Jenkins API token                                                                                                                                             | ✅       |
| `OCEAN__INTEGRATION__CONFIG__JENKINS_HOST`        | The Jenkins host. For example https://jenkins.io                                                                                                                   | ✅       |
| `OCEAN__INTEGRATION__CONFIG__JENKINS_ORGANIZATION`| The Jenkins organization slug                                                                                                                                     | ✅       |
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
        stage('Run Jenkins Integration') {
            steps {
                script {
                    withCredentials([
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_TOKEN', variable: 'OCEAN__INTEGRATION__CONFIG__J_TOKEN'),
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_HOST', variable: 'OCEAN__INTEGRATION__CONFIG__JENKINS_HOST'),
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_ORGANIZATION', variable: 'OCEAN__INTEGRATION__CONFIG__JENKINS_ORGANIZATION'),
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
                                -e OCEAN__INTEGRATION__CONFIG__JENKINS_TOKEN=$OCEAN__INTEGRATION__CONFIG__JENKINS_TOKEN \
                                -e OCEAN__INTEGRATION__CONFIG__JENKINS_HOST=$OCEAN__INTEGRATION__CONFIG__JENKINS_HOST \
                                -e OCEAN__INTEGRATION__CONFIG__JENKINS_ORGANIZATION=$OCEAN__INTEGRATION__CONFIG__JENKINS_ORGANIZATION \
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

## Ingesting Jenkins objects

The Jenkins integration uses a YAML configuration to describe the process of loading data into the developer portal.

Here is an example snippet from the config which demonstrates the process for getting `Job` data from Jenkins:

```yaml showLineNumbers
resources:
  - kind: job
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .name
          title: .name
          blueprint: '"jenkinsJob"'
          properties:
            jobIsBuildable: .buildable
            jobUrl: .url
            description: .description
            color: .color

```

The integration makes use of the [JQ JSON processor](https://stedolan.github.io/jq/manual/) to select, modify, concatenate, transform and perform other operations on existing fields and values from Jenkins' API events.

### Configuration structure

The integration configuration determines which resources will be queried from Jenkins, and which entities and properties will be created in Port.

:::tip Supported resources
The following resources can be used to map data from Jenkins, it is possible to reference any field that appears in the API responses linked below for the mapping configuration.

- [`Job`](https://wiki.jenkins-ci.org/display/JENKINS/Remote+access+API)
- [`Builds`](https://wiki.jenkins-ci.org/display/JENKINS/Remote+access+API)

:::

- The root key of the integration configuration is the `resources` key:

  ```yaml showLineNumbers
  # highlight-next-line
  resources:
    - kind: job
      selector:
      ...
  ```

- The `kind` key is a specifier for a Jenkins object:

  ```yaml showLineNumbers
    resources:
      # highlight-next-line
      - kind: build
        selector:
        ...
  ```

- The `port`, `entity` and the `mappings` keys are used to map the Jenkins object fields to Port entities. To create multiple mappings of the same kind, you can add another item in the `resources` array;

  ```yaml showLineNumbers
    resources:
    - kind: job
        selector:
        query: "true"
        port:
        entity:
            mappings:
            identifier: .name
            title: .name
            blueprint: '"jenkinsJob"'
            properties:
                jobIsBuildable: .buildable
                jobUrl: .url
                description: .description
                color: .color
  ```

  :::tip Blueprint key
  Note the value of the `blueprint` key - if you want to use a hardcoded string, you need to encapsulate it in 2 sets of quotes, for example use a pair of single-quotes (`'`) and then another pair of double-quotes (`"`)
  :::

### Ingest data into Port

To ingest Jenkins objects using the [integration configuration](#configuration-structure), you can follow the steps below:

1. Go to the DevPortal Builder page.
2. Select a blueprint you want to ingest using Jenkins.
3. Choose the **Ingest Data** option from the menu.
4. Select Jenkins under the CI/CD Pipeline category.
5. Add the contents of your [integration configuration](#configuration-structure) to the editor.
6. Click `Resync`.

## Examples

Examples of blueprints and the relevant integration configurations:

### Job

<details>
<summary>Job blueprint</summary>

```json showLineNumbers
{
"identifier": "jenkinsBuild",
"description": "This blueprint represents a build event from Jenkins",
"title": "Jenkins Build",
"icon": "Jenkins",
"schema": {
    "properties": {
    "buildStatus": {
        "type": "string",
        "title": "Build Status",
        "enum": [
        "SUCCESS",
        "FAILURE",
        "UNSTABLE"
        ],
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
"aggregationProperties": {},
"relations": {
    "jenkinsJob": {
    "title": "Jenkins Job",
    "target": "jenkinsJob",
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
resources:
  - kind: job
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .name
          title: .name
          blueprint: '"jenkinsJob"'
          properties:
            jobIsBuildable: .buildable
            jobUrl: .url
            description: .description
            color: .color
```

</details>

### Build

<details>
<summary>Build blueprint</summary>

```json showLineNumbers
{
"identifier": "jenkinsJob",
"description": "This blueprint represents a job event from Jenkins",
"title": "Jenkins Job",
"icon": "Jenkins",
"schema": {
    "properties": {
    "jobIsBuildable": {
        "type": "boolean",
        "title": "Buildable",
        "description": "Indicates whether job is buildable or not"
    },
    "description": {
        "type": "string",
        "title": "Job Description",
        "description": "Job description"
    },
    "jobUrl": {
        "type": "string",
        "description": "Url of jenkins job"
    },
    "color": {
        "type": "string",
        "description": "jenkins job color"
    }
    },
    "required": []
},
"mirrorProperties": {},
"calculationProperties": {},
"aggregationProperties": {},
"relations": {}
}
```

</details>

<details>
<summary>Integration configuration</summary>

```yaml showLineNumbers
- kind: build
selector:
    query: "true"
port:
    entity:
    mappings:
        identifier: .id
        title: .fullDisplayName
        blueprint: '"jenkinsBuild"'
        properties:
        buildStatus: .result
        buildUrl: .url
        timestamp: .timestamp | (todateiso8601 | gsub("T"; " ") | sub("\\.[0-9]+Z$"; "") | sub("^(?<year>[0-9]{4})-(?<month>[0-9]{2})-(?<day>[0-9]{2})"; .day + "/" + .month + "/" + .year) | sub(" (?<hour>[0-9]{2}:[0-9]{2}):[0-9]{2}"; " " + .hour))|gsub("Z";"")
        buildDuration: .duration
        relations:
        jenkinsJob: .fullDisplayName | split(" ")[0]
```

</details>

## Let's Test It

This section includes a sample response data from Jenkins. In addition, it includes the entity created from the resync event based on the Ocean configuration provided in the previous section.

### Payload

Here is an example of the payload structure from Jenkins:

<details>
<summary> Build response data</summary>

```json showLineNumbers
{
      "_class":"hudson.model.FreeStyleBuild",
      "actions":[
         {
            "_class":"hudson.model.CauseAction",
            "causes":[
               {
                  "_class":"hudson.model.Cause$UserIdCause",
                  "shortDescription":"Started by user John Doe",
                  "userId":"jdoe",
                  "userName":"John Doe"
               }
            ]
         },
         {
            
         },
         {
            "_class":"org.jenkinsci.plugins.displayurlapi.actions.RunDisplayAction"
         }
      ],
      "artifacts":[
         
      ],
      "building":false,
      "description":"None",
      "displayName":"#9",
      "duration":134,
      "estimatedDuration":417,
      "executor":"None",
      "fullDisplayName":"PortJenkins #9",
      "id":"9",
      "inProgress":false,
      "keepLog":false,
      "number":9,
      "queueId":15,
      "result":"SUCCESS",
      "timestamp":1701465825741,
      "url":"https://localhost:8080/job/PortJenkins/9/",
      "builtOn":"",
      "changeSet":{
         "_class":"hudson.scm.EmptyChangeLogSet",
         "items":[
            
         ],
         "kind":"None"
      },
      "culprits":[
         
      ]
   }

```

</details>

<details>
<summary> Jobs response data</summary>

```json showLineNumbers
{
   "_class":"hudson.model.FreeStyleProject",
   "actions":[
      {},
      {},
      {
         "_class":"org.jenkinsci.plugins.displayurlapi.actions.JobDisplayAction"
      },
      {
         "_class":"com.cloudbees.plugins.credentials.ViewCredentialsAction"
      }
   ],
   "description":"None",
   "displayName":"portJenkins",
   "displayNameOrNull":"None",
   "fullDisplayName":"portJenkins",
   "fullName":"portJenkins",
   "name":"portJenkins",
   "url":"https://localhost:9090/job/PortJenkins/",
   "buildable":true,
   "builds":[
      {
         "_class":"hudson.model.FreeStyleBuild",
         "number":6,
         "url":"https://localhost:9090/job/PortJenkins/6/"
      },
      {
         "_class":"hudson.model.FreeStyleBuild",
         "number":5,
         "url":"https://localhost:9090/job/PortJenkins/5/"
      },
      {
         "_class":"hudson.model.FreeStyleBuild",
         "number":4,
         "url":"https://localhost:9090/job/PortJenkins/4/"
      },
      {
         "_class":"hudson.model.FreeStyleBuild",
         "number":3,
         "url":"https://localhost:9090/job/PortJenkins/3/"
      },
      {
         "_class":"hudson.model.FreeStyleBuild",
         "number":2,
         "url":"https://localhost:9090/job/PortJenkins/2/"
      },
      {
         "_class":"hudson.model.FreeStyleBuild",
         "number":1,
         "url":"https://localhost:9090/job/PortJenkins/1/"
      }
   ],
   "color":"blue",
   "firstBuild":{
      "_class":"hudson.model.FreeStyleBuild",
      "number":1,
      "url":"https://localhost:9090/job/PortJenkins/1/"
   },
   "healthReport":[
      {
         "description":"Build stability: No recent builds failed.",
         "iconClassName":"icon-health-80plus",
         "iconUrl":"health-80plus.png",
         "score":100
      }
   ],
   "inQueue":false,
   "keepDependencies":false,
   "lastBuild":{
      "_class":"hudson.model.FreeStyleBuild",
      "number":6,
      "url":"https://localhost:9090/job/PortJenkins/6/"
   },
   "lastCompletedBuild":{
      "_class":"hudson.model.FreeStyleBuild",
      "number":6,
      "url":"https://localhost:9090/job/PortJenkins/6/"
   },
   "lastFailedBuild":"None",
   "lastStableBuild":{
      "_class":"hudson.model.FreeStyleBuild",
      "number":6,
      "url":"https://localhost:9090/job/PortJenkins/6/"
   },
   "lastSuccessfulBuild":{
      "_class":"hudson.model.FreeStyleBuild",
      "number":6,
      "url":"https://localhost:9090/job/PortJenkins/6/"
   },
   "lastUnstableBuild":"None",
   "lastUnsuccessfulBuild":"None",
   "nextBuildNumber":7,
   "property":[
      
   ],
   "queueItem":"None",
   "concurrentBuild":false,
   "disabled":false,
   "downstreamProjects":[
      
   ],
   "labelExpression":"None",
   "scm":{
      "_class":"hudson.scm.NullSCM"
   },
   "upstreamProjects":[
      
   ]
}
```

</details>

### Mapping Result

The combination of the sample payload and the Ocean configuration generates the following Port entity:

<details>
<summary> Job entity in Port</summary>

```json showLineNumbers
{
  "identifier": "PortJenkins",
  "title": "PortJenkins",
  "team": [],
  "properties": {
    "jobIsBuildable": true,
    "description": "Sync Jobs and Builds to Port Ocean",
    "jobUrl": "https://localhost:9090/job/PortJenkins/",
    "color": "blue"
  },
  "relations": {},
  "icon": "Jenkins"
}
```

</details>

<details>
<summary> Build entity in Port</summary>

```json showLineNumbers
{
  "identifier": "9",
  "title": "PortJenkins #9",
  "team": [],
  "properties": {
    "buildStatus": "SUCCESS",
    "buildUrl": "http://localhost:9090/job/PortJenkins/9/",
    "buildDuration": 134
  },
  "relations": {
    "jenkinsJob": "PortJenkins"
  },
  "icon": "Jenkins"
}
```

</details>