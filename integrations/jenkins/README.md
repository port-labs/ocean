# Jenkins

An integration used to import Jenkins resources into Port.

## Common use cases

- Define mappings for Jenkins jobs and builds within your project's environment.
- Monitor real-time changes in Jenkins objects (creation, updates, deletions) and seamlessly synchronize these changes with corresponding entities in Port.

## installation

### Real Time & Always On

Using this installation option means that the integration will be able to update Port in real time using webhooks.


```bash showLineNumbers
helm repo add --force-update port-labs https://port-labs.github.io/helm-charts
helm upgrade --install my-jenkins-integration port-labs/port-ocean \
	--set port.clientId="PORT_CLIENT_ID"  \
	--set port.clientSecret="PORT_CLIENT_SECRET"  \
	--set port.baseUrl="https://api.getport.io"  \
	--set initializePortResources=true  \
	--set scheduledResyncInterval=120 \
	--set integration.identifier="my-jenkins-integration"  \
	--set integration.type="jenkins"  \
	--set integration.eventListener.type="POLLING"  \
	--set integration.config.jenkinsHost="string"  \
	--set integration.secrets.jenkinsUser="string"  \
	--set integration.secrets.jenkinsPassword="string"
```

## Ingesting Jenkins objects

The Jenkins integration uses a YAML configuration to describe the process of loading data into the developer portal.

Here is an example snippet from the config which demonstrates the process for getting `job` data from Jenkins:

```yaml showLineNumbers
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
  - kind: job
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: '.url | sub("%20"; "-"; "g") | sub("/"; "-"; "g") | .[:-1]'
```

The integration makes use of the [JQ JSON processor](https://stedolan.github.io/jq/manual/) to select, modify, concatenate, transform and perform other operations on existing fields and values from Jira's API events.


## Examples

Examples of blueprints and the relevant integration configurations:

### Job

<details>
<summary>Job blueprint</summary>

```json showLineNumbers
{
  "identifier": "jenkinsJob",
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
      }
    },
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {
    "jobUrl": {
      "title": "Job Full URL",
      "calculation": "'https://your_jenkins_url/' + .properties.url",
      "type": "string",
      "format": "url"
    }
  },
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
      query: "true"
    port:
      entity:
        mappings:
          identifier: '.url | sub("%20"; "-"; "g") | sub("/"; "-"; "g") | .[:-1]'
          title: .displayName
          blueprint: '"jenkinsJob"'
          properties:
            jobName: .fullName
            url: .url
            jobStatus: . | split(\".\") | last
            timestamp: .time
```
</details>


### Build

<details>
<summary>Build blueprint</summary>

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
          blueprint: '"jenkinsBuild"'
          properties:
            buildStatus: .result,
            buildUrl: .url,
            buildDuration: .duration,
            timestamp: .timestamp
          relations:
            job: '.source | tostring | sub("%20"; "-"; "g") | sub("/"; "-"; "g") | .[:-1]'
```
</details>
