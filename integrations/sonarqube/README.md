# Sonarqube

Sonarqube project and code quality integration for Port using Port-Ocean Framework.

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

## Installation
For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration at your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.secrets.sonarApiToken: The Sonarqube API token
# integration.config.appHost: The Sonarqube app host
# integration.config.sonarUrl: The url of the Sonarqube instance or server. If not specified, the default will be https://sonarcloud.io
# integration.config.sonarOrganizationId: The Sonarqube organization ID

helm upgrade --install my-sonarqube-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
	--set integration.identifier="my-sonarqube-integration"  \
	--set integration.type="sonarqube"  \
	--set integration.eventListener.type="POLLING"  \
	--set integration.secrets.sonarApiToken="token"  \
```
## Supported Kinds
As of the latest version `(0.1.3)` of the Sonarqube integration, the analysis object kind is skipped when an on-premise Sonarqube server is being used.

### Project
This kind represents a Sonarqube project. Retrieves data from [Sonarqube components](https://next.sonarqube.com/sonarqube/web_api/api/components) and [Sonarqube measures](https://next.sonarqube.com/sonarqube/web_api/api/measures) and [Sonarque branches](https://next.sonarqube.com/sonarqube/web_api/api/project_branches)

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier": "sonarQubeProject",
    "title": "SonarQube Project",
    "icon": "sonarqube",
    "schema": {
      "properties": {
        "organization": {
          "type": "string",
          "title": "Organization",
          "icon": "TwoUsers"
        },
        "link": {
          "type": "string",
          "format": "url",
          "title": "Link",
          "icon": "Link"
        },
        "lastAnalysisStatus": {
          "type": "string",
          "title": "Last Analysis Status",
          "enum": [
            "PASSED",
            "OK",
            "FAILED",
            "ERROR"
          ],
          "enumColors": {
            "PASSED": "green",
            "OK": "green",
            "FAILED": "red",
            "ERROR": "red"
          }
        },
        "lastAnalysisDate": {
          "type": "string",
          "format": "date-time",
          "icon": "Clock",
          "title": "Last Analysis Date"
        },
        "numberOfBugs": {
          "type": "number",
          "title": "Number Of Bugs"
        },
        "numberOfCodeSmells": {
          "type": "number",
          "title": "Number Of CodeSmells"
        },
        "numberOfVulnerabilities": {
          "type": "number",
          "title": "Number Of Vulnerabilities"
        },
        "numberOfHotSpots": {
          "type": "number",
          "title": "Number Of HotSpots"
        },
        "numberOfDuplications": {
          "type": "number",
          "title": "Number Of Duplications"
        },
        "coverage": {
          "type": "number",
          "title": "Coverage"
        },
        "mainBranch": {
          "type": "string",
          "icon": "Git",
          "title": "Main Branch"
        },
        "tags": {
          "type": "array",
          "title": "Tags"
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
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: projects
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          blueprint: '"sonarQubeProject"'
          identifier: .key
          title: .name
          properties:
              organization: .organization
              link: .link
              lastAnalysisStatus: .branch.status.qualityGateStatus
              lastAnalysisDate: .analysisDateAllBranches
              numberOfBugs: .measures[]? | select(.metric == "bugs") | .value
              numberOfCodeSmells: .measures[]? | select(.metric == "code_smells") | .value
              numberOfVulnerabilities: .measures[]? | select(.metric == "vulnerabilities") | .value
              numberOfHotSpots: .measures[]? | select(.metric == "security_hotspots") | .value
              numberOfDuplications: .measures[]? | select(.metric == "duplicated_files") | .value
              coverage: .measures[]? | select(.metric == "coverage") | .value
              mainBranch: .branch.name
              tags: .tags
```
</details>

### Issues
This kind represents a Sonarqube issue. It relies on data from [Sonarqube issues](https://next.sonarqube.com/sonarqube/web_api/api/issues)

<details>
<summary>blueprint.json</summary>

```json
 {
    "identifier": "sonarQubeIssue",
    "title": "SonarQube Issue",
    "icon": "sonarqube",
    "schema": {
      "properties": {
        "type": {
          "type": "string",
          "title": "Type",
          "enum": [
            "CODE_SMELL",
            "BUG",
            "VULNERABILITY"
          ]
        },
        "severity": {
          "type": "string",
          "title": "Severity",
          "enum": [
            "MAJOR",
            "INFO",
            "MINOR",
            "CRITICAL",
            "BLOCKER"
          ],
          "enumColors": {
            "MAJOR": "orange",
            "INFO": "green",
            "CRITICAL": "red",
            "BLOCKER": "red",
            "MINOR": "yellow"
          }
        },
        "link": {
          "type": "string",
          "format": "url",
          "icon": "Link",
          "title": "Link"
        },
        "status": {
          "type": "string",
          "title": "Status",
          "enum": [
            "OPEN",
            "CLOSED",
            "RESOLVED",
            "REOPENED",
            "CONFIRMED"
          ]
        },
        "assignees": {
          "title": "Assignees",
          "type": "string",
          "icon": "TwoUsers"
        },
        "tags": {
          "type": "array",
          "title": "Tags"
        },
        "createdAt": {
          "type": "string",
          "format": "date-time",
          "title": "Created At"
        }
      }
    },
    "relations": {
      "sonarQubeProject": {
        "target": "sonarQubeProject",
        "required": false,
        "title": "SonarQube Project",
        "many": false
      }
    }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: issues
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          blueprint: '"sonarQubeIssue"'
          identifier: .key
          title: .message
          properties:
              type: .type
              severity: .severity
              link: .link
              status: .status
              assignees: .assignee
              tags: .tags
              createdAt: .creationDate
          relations:
            sonarQubeProject: .project

```
</details>

### Analysis
This kind represents a Sonarqube analysis and latest activity.

<details>
<summary>blueprint.json</summary>

```json
  {
    "identifier": "sonarQubeAnalysis",
    "title": "SonarQube Analysis",
    "icon": "sonarqube",
    "schema": {
      "properties": {
        "branch": {
          "type": "string",
          "title": "Branch",
          "icon": "GitVersion"
        },
        "fixedIssues": {
          "type": "number",
          "title": "Fixed Issues"
        },
        "newIssues": {
          "type": "number",
          "title": "New Issues"
        },
        "coverage": {
          "title": "Coverage",
          "type": "number"
        },
        "duplications": {
          "type": "number",
          "title": "Duplications"
        },
        "createdAt": {
          "type": "string",
          "format": "date-time",
          "title": "Created At"
        }
      }
    },
    "relations": {
      "sonarQubeProject": {
        "target": "sonarQubeProject",
        "required": false,
        "title": "SonarQube Project",
        "many": false
      }
    }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: analysis
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          blueprint: '"sonarQubeAnalysis"'
          identifier: .analysisId
          title: .commit.message
          properties:
              branch: .branch_name
              fixedIssues: .measures.violations_fixed
              newIssues: .measures.violations_added
              coverage: .measures.coverage_change
              duplications: .measures.duplicated_lines_density_change
              createdAt: .analysis_date
          relations:
            sonarQubeProject: .project
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
The Sonarqube integration suggested folder structure is as follows:

```
sonarqube/
├─ sonarqub_integration/             # The integration logic
│  ├─ sonarqube_client.py      # Wrapper to the Sonarqube REST API and other custom integration logic
├─ main.py              # The main exports the custom Ocean logic to the ocean sail command
├─ pyproject.toml
└─ Dockerfile
```