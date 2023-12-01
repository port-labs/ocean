# Jenkins

Our Jenkins integration allows you to import `jobs` and `builds` from your Jenkins installation running on a server into Port, according to your mapping and definition.

## Common use cases

- Map jobs and builds in your Jenkins environment
- View status of Jenkins jobs and builds from your Port dashboard

## Prerequisites

To install the integration, you need [Jenkins](https://www.jenkins.io/) installed on your server. The port Jenkins runs on should be exposed to outside traffic as Port will ping this port to ingest data.

After installing Jenkins, you should be armed to the teeth with the following information:

- Jekins username
- Jenkins password
- URL pointing to where Jenkins is running

## Installation

Choose one of the following installation methods:

### Real Time & Always On

Using this installation option means that the integration will be able to update Port in real time using webhooks.

This table summarizes the available parameters for the installation. Set them as you wish in the script below, then copy it and run it in your terminal:

| Parameters                                | Descriptions                                                                                                          | Required |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | -------- |
| port.clientId                             | Your port client id                                                                                                   | ✅       |
| port.clientSecret                         | Your port client secret                                                                                               | ✅       |
| port.baseUrl                              | Your port base url, relevant only if not using the default port app                                                   | ❌       |
| integration.identifier                    | Change the identifier to describe your integration                                                                    | ✅       |
| integration.type                          | The integration type                                                                                                  | ✅       |
| integration.eventListener.type            | The event listener type                                                                                               | ✅       |
| integration.secrets.jenkinsUsername       | Your Jenkins username                                                                                                 | ✅       |
| integration.secrets.jenkinsPassword       | Your Jenkins password                                                                                                 | ✅       |
| integration.config.jenkinsHost            | The host URL for your Jenkins installation                                                                            | ✅       |
| integration.config.jenkinsBuildsBatchSize | The number of builds that will be loaded per batch. Defaults to 100                                                   | ❌       |
| integration.config.jenkinsJobsBatchSize   | The number of jobs that will be loaded per batch. Defaults to 100                                                     | ❌       |
| integration.config.appHost                | The host of the Port Ocean app. Used to set up the integration endpoint as the target for webhooks created in Jenkins | ❌       |
| scheduledResyncInterval                   | The number of minutes between each resync                                                                             | ❌       |
| initializePortResources                   | Default true, When set to true the integration will create default blueprints and the port App config Mapping         | ❌       |

```bash
helm repo add --force-update port-labs https://port-labs.github.io/helm-charts
helm upgrade --install my-jenkins-integration port-labs/port-ocean \
	--set port.clientId="PORT_CLIENT_ID"  \
	--set port.clientSecret="PORT_CLIENT_SECRET"  \
	--set port.baseUrl="https://api.getport.io"  \
	--set initializePortResources=true  \
	--set scheduledResyncInterval=120 \
	--set integration.identifier="my-jenkins-integration"  \
	--set integration.type="jenkins"  \
	--set integration.eventListener.type="POLLING" \
	--set integration.config.jenkinsHost="string"  \
	--set integration.config.jenkinsBuildsBatchSize="int"  \
	--set integration.config.jenkinsJobsBatchSize="int"  \
	--set integration.secrets.jenkinsUsername="string"  \
	--set integration.secrets.jenkinsPassword="string"  \

```

### One Time

#### GitHub

This workflow will run the Jenkins integration once and then exit, this is useful for one time ingestion of data.

_Warning: If you want the integration to update Port in real time using webhooks you should use the Real Time & Always On installation option._

Make sure to configure the following [Github Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions):

| Parameters                                              | Descriptions                                                                                                       | Required |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------- |
| OCEAN**PORT**CLIENT_ID                                  | Your port client id                                                                                                | ✅       |
| OCEAN**PORT**CLIENT_SECRET                              | Your port client secret                                                                                            | ✅       |
| OCEAN**PORT**BASE_URL                                   | Your port base url, relevant only if not using the default port app                                                | ❌       |
| OCEAN**INTEGRATION**IDENTIFIER                          | Change the identifier to describe your integration                                                                 | ❌       |
| OCEAN\_\_INITIALIZE_PORT_RESOURCES                      | Default true, When set to false the integration will not create default blueprints and the port App config Mapping | ❌       |
| OCEAN**INTEGRATION**CONFIG\_\_JENKINS_USERNAME          | Your Jenkins username                                                                                              | ✅       |
| OCEAN**INTEGRATION**CONFIG\_\_JENKINS_PASSWORD          | Your Jenkins password                                                                                              | ✅       |
| OCEAN**INTEGRATION**CONFIG\_\_JENKINS_HOST              | The host URL for your Jenkins installation                                                                         | ✅       |
| OCEAN**INTEGRATION**CONFIG\_\_JENKINS_BUILDS_BATCH_SIZE | The number of builds that will be loaded per batch. Defaults to 100                                                | ❌       |
| OCEAN**INTEGRATION**CONFIG\_\_JENKINS_JOBS_BATCH_SIZE   | The number of jobs that will be loaded per batch. Defaults to 100                                                  | ❌       |

Here is an example for `jenkins-integration.yml` workflow file:

```yaml
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
          -e OCEAN__INTEGRATION__CONFIG__JENKINS_USERNAME=${{ secrets.OCEAN__INTEGRATION__CONFIG__JENKINS_USERNAME }} \
          -e OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD=${{ secrets.OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD }} \
          -e OCEAN__INTEGRATION__CONFIG__JENKINS_BUILDS_BATCH_SIZE=${{ secrets.OCEAN__INTEGRATION__CONFIG__JENKINS_BUILDS_BATCH_SIZE }} \
          -e OCEAN__INTEGRATION__CONFIG__JENKINS_JOBS_BATCH_SIZE=${{ secrets.OCEAN__INTEGRATION__CONFIG__JENKINS_JOBS_BATCH_SIZE }} \
          -e OCEAN__PORT__CLIENT_ID=${{ secrets.OCEAN__PORT__CLIENT_ID }} \
          -e OCEAN__PORT__CLIENT_SECRET=${{ secrets.OCEAN__PORT__CLIENT_SECRET }} \
          $image_name
```

#### Jenkins

This pipeline will run the Jenkins integration once and then exit, this is useful for one time ingestion of data.

_Tip: Your Jenkins agent should be able to run docker commands._

_Warning: If you want the integration to update Port in real time using webhooks you should use the Real Time & Always On installation option._

Make sure to configure the following [Jenkins Credentials](https://www.jenkins.io/doc/book/using/using-credentials/) of `Secret Text` type:

| Parameters                                              | Descriptions                                                                                                       | Required |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | -------- |
| OCEAN**PORT**CLIENT_ID                                  | Your port client id                                                                                                | ✅       |
| OCEAN**PORT**CLIENT_SECRET                              | Your port client secret                                                                                            | ✅       |
| OCEAN**PORT**BASE_URL                                   | Your port base url, relevant only if not using the default port app                                                | ❌       |
| OCEAN**INTEGRATION**IDENTIFIER                          | Change the identifier to describe your integration                                                                 | ❌       |
| OCEAN\_\_INITIALIZE_PORT_RESOURCES                      | Default true, When set to false the integration will not create default blueprints and the port App config Mapping | ❌       |
| OCEAN**INTEGRATION**CONFIG\_\_JENKINS_USERNAME          | Your Jenkins username                                                                                              | ✅       |
| OCEAN**INTEGRATION**CONFIG\_\_JENKINS_PASSWORD          | Your Jenkins password                                                                                              | ✅       |
| OCEAN**INTEGRATION**CONFIG\_\_JENKINS_HOST              | The host URL for your Jenkins installation                                                                         | ✅       |
| OCEAN**INTEGRATION**CONFIG\_\_JENKINS_BUILDS_BATCH_SIZE | The number of builds that will be loaded per batch. Defaults to 100                                                | ❌       |
| OCEAN**INTEGRATION**CONFIG\_\_JENKINS_JOBS_BATCH_SIZE   | The number of jobs that will be loaded per batch. Defaults to 100                                                  | ❌       |

Here is an example for Jenkinsfile groovy pipeline file:

```Jenkinsfile
pipeline {
    agent any

    stages {
        stage('Run Jenkins Integration') {
            steps {
                script {
                    withCredentials([
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_HOST', variable: 'OCEAN__INTEGRATION__CONFIG__JENKINS_HOST'),
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_USERNAME', variable: 'OCEAN__INTEGRATION__CONFIG__JENKINS_USERNAME'),
                        string(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD', variable: 'OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD'),
                        int(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_BUILDS_BATCH_SIZE', variable: 'OCEAN__INTEGRATION__CONFIG__JENKINS_BUILDS_BATCH_SIZE'),
                        int(credentialsId: 'OCEAN__INTEGRATION__CONFIG__JENKINS_JOBS_BATCH_SIZE', variable: 'OCEAN__INTEGRATION__CONFIG__JENKINS_JOBS_BATCH_SIZE'),
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
                                -e OCEAN__INTEGRATION__CONFIG__JENKINS_USERNAME=$OCEAN__INTEGRATION__CONFIG__JENKINS_USERNAME \
                                -e OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD=$OCEAN__INTEGRATION__CONFIG__JENKINS_PASSWORD \
                                -e
                                // Both batch sizes config can be left out if you wish to use the default.
                                OCEAN__INTEGRATION__CONFIG__JENKINS_BUILDS_BATCH_SIZE=$OCEAN__INTEGRATION__CONFIG__JENKINS_BUILDS_BATCH_SIZE \
                                -e OCEAN__INTEGRATION__CONFIG__JENKINS_JOBS_BATCH_SIZE=$OCEAN__INTEGRATION__CONFIG__JENKINS_JOBS_BATCH_SIZE \
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

## Ingesting Jenkins objects

The Jenkins integration uses a YAML configuration to describe the process of loading data into the developer portal.

Here is an example snippet from the config which demonstrates the process for getting project data from Jenkins:

```yaml
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
  - kind: job
    selector:
      query: "true"
    port:
      entity:
        mappings:
          blueprint: '"job"'
          identifier: .url
          title: .name
          properties:
            timestamp: '.timestamp |= (. / 1000 | strftime("%Y-%m-%d %H:%M:%S %Z"))'
```

The integration makes use of the [JQ JSON processor](https://stedolan.github.io/jq/manual/) to select, modify, concatenate, transform and perform other operations on existing fields and values from Jenkins's API events.

### Configuration structure

The integration configuration determines which resources will be queried from Jenkins, and which entities and properties will be created in Port.

_SUPPORTED RESOURCES:
The following resources can be used to map data from Jenkins, it is possible to reference any field that appears in the API responses linked below for the mapping configuration._

- _Job_
- _Build_

- The root key of the integration configuration is the resources key:

```yaml
resources:
  - kind: job
    selector:
    ...
```

- The kind key is a specifier for a Jenkins object:

```yaml
resources:
  - kind: job
    selector:
```

- The `selector` and the `query` keys allow you to filter which objects of the specified `kind` will be ingested into your software catalog:

```yaml
resources:
  - kind: job
    selector:
      query: "true" # JQ boolean expression. If evaluated to false - this object will be skipped.
    port:
```

- The `port`, `entity` and the `mappings` keys are used to map the Jenkins object fields to Port entities. To create multiple mappings of the same kind, you can add another item in the `resources` array;

```yaml
resources:
  - kind: job
    selector:
      query: "true"
    port:
      entity:
        mappings: # Mappings between one Jenkins object to a Port entity. Each value is a JQ query.
          blueprint: '"job"'
          identifier: .url
          title: .name
          properties:
            name: .name
  - kind: job # In this instance project is mapped again with a different filter
    selector:
      query: '.name == "MyJobName'
    port:
      entity:
        mappings: ...
```

_BLUEPRINT KEY
Note the value of the blueprint key - if you want to use a hardcoded string, you need to encapsulate it in 2 sets of quotes, for example use a pair of single-quotes (') and then another pair of double-quotes (")_

### Ingest data into Port

To ingest Jenkins objects using the [integration configuration](#configuration-structure), you can follow the steps below:

1. Go to the DevPortal Builder page.
2. Select a blueprint you want to ingest using Jenkins.
3. Choose the Ingest Data option from the menu.
4. Select Jenkins under the GitOps category.
5. Modify the configuration according to your needs.
6. Click Resync.

## Examples

Examples of blueprints and the relevant integration configurations:

### Job

Job blueprint

```json
{
    "identifier": "job",
    "description": "This blueprint represents a job event from Jenkins",
    "title": "Jenkins Job",
    "icon": "Jenkins",
    "schema": {
      "properties": {
        "name": {
          "type": "string",
          "title": "Job Name"
        },
        "status": {
          "type": "string",
          "title": "Last Build Status",
          "enum": ["SUCCESS", "FAILURE", "UNSTABLE"],
          "enumColors": {
            "SUCCESS": "green",
            "FAILURE": "red",
            "UNSTABLE": "yellow"
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
          "title": "Job URL"
        }
      },
      "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {}
  },
```

**Integration configuration**

```yaml
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
  - kind: job
    selector:
      query: "true"
    port:
      entity:
        mappings:
          blueprint: '"job"'
          identifier: .url
          title: .name
          properties:
            name: .name
            url: .url
            status: .lastBuild.result
            timestamp: '.timestamp |= (. / 1000 | strftime("%Y-%m-%d %H:%M:%S %Z"))'
```

### Build

**Build blueprint**

```json
{
  "identifier": "build",
  "description": "This blueprint represents a build event from Jenkins",
  "title": "Jenkins Build",
  "icon": "Jenkins",
  "schema": {
    "properties": {
      "id": {
        "type": "string",
        "title": "Build ID",
        "description": "ID of the build"
      },
      "name": {
        "type": "string",
        "title": "Build name",
        "description": "Full display name of the build"
      },
      "status": {
        "type": "string",
        "title": "Build Status",
        "enum": ["SUCCESS", "FAILURE", "UNSTABLE"],
        "enumColors": {
          "SUCCESS": "green",
          "FAILURE": "red",
          "UNSTABLE": "yellow"
        }
      },
      "url": {
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
      "duration": {
        "type": "string",
        "title": "Build Duration",
        "description": "Duration of the build"
      },
      "jobUrl": {
        "type": "string",
        "title": "Job URL",
        "description": "URL to the job"
      }
    },
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {},
  "relations": {
    "jobUrl": {
      "title": "Jenkins Job",
      "target": "job",
      "required": false,
      "many": false
    }
  }
}
```

**Integration configuration**

```yaml
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
  - kind: build
    selector:
      query: "true"
    port:
      entity:
        mappings:
          blueprint: '"build"'
          identifier: .url
          title: .fullDisplayName
          properties:
            id: .id
            name: .fullDisplayName
            status: .result
            url: .url
            timestamp: '.timestamp |= (. / 1000 | strftime("%Y-%m-%d %H:%M:%S %Z"))'
            duration: '.duration |= (. / 1000 | sprintf("%.2fsec"))'
            jobUrl: '.url |= (. | sub("/[0-9]+/$"; ""))'
          relations:
            job: '.url |= (. | sub("/[0-9]+/$"; ""))'
```

## Let's Test It

This section includes a sample response data from Jenkins. In addition, it includes the entity created from the resync event based on the Ocean configuration provided in the previous section.

### Payload

Here is an example of the payload structure from Jenkins:

**Job response data:**

```json
{
  "_class": "hudson.model.FreeStyleProject",
  "name": "Stuff jub",
  "url": "http://localhost:8080/job/Stuff%20jub/",
  "lastBuild": {
    "_class": "hudson.model.FreeStyleBuild",
    "result": "SUCCESS",
    "timestamp": 1700709021342
  }
}
```

**Build response data:**

```json
{
  "_class" : "hudson.model.FreeStyleBuild",
  "duration" : 287,
  "fullDisplayName" : "Stuff jub #4",
  "id" : "4",
  "result" : "SUCCESS",
  "timestamp" : 1700709021342,
  "url" : "http://localhost:8080/job/Stuff%20jub/4/"
},
```
