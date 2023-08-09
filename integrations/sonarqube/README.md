# Sonarqube

Sonarqube project and code quality integration for Port using Port-Ocean Framework

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
	--set integration.triggerChannel.type="POLLING"  \
	--set integration.secrets.sonarApiToken="token"  \
	--set integration.config.appHost="https://example.com"  \
    --set integration.config.sonarUrl="https://sonarcloud.io"  \
    --set integration.config.sonarOrganizationId="my-organization"  \
```
## Supported Kinds
### cloudAnalysis
This kind represents a Sonarqube code quality analysis with project information.

<details>
<summary>blueprint.json</summary>

```json
{
	"identifier": "sonarCodeAnalysis",
	"description": "This blueprint represents a SonarCloud Analysis in our software catalog",
	"title": "SonarQube Code Analysis",
	"icon": "sonarqube",
	"schema": {
		"properties": {
			"serverUrl": {
				"type": "string",
				"format": "url",
				"title": "Server URL"
			},
			"projectUrl": {
				"type": "string",
				"format": "url",
				"title": "Project URL"
			},
			"branchName": {
				"type": "string",
				"title": "Branch Name"
			},
			"branchType": {
				"type": "string",
				"title": "Branch Type"
			},
			"qualityGateName": {
				"type": "string",
				"title": "Quality Gate Name"
			},
			"qualityGateStatus": {
				"type": "string",
				"title": "Quality Gate Status",
				"enum": ["OK", "WARN", "ERROR", "NONE"],
				"enumColors": {
					"OK": "green",
					"WARN": "yellow",
					"ERROR": "red",
					"NONE": "lightGray"
				}
			},
			"qualityGateConditions": {
				"type": "array",
				"items": {
					"type": "object"
				},
				"title": "Quality Gate Conditions"
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
  - kind: cloudAnalysis
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          blueprint: '"sonarCodeAnalysis"'
          identifier: .project_key
          title: .project_name
          properties:
              serverUrl: .server_url
              projectUrl: .project_url
              branchName: .branch_name
              branchType: .branch_type
              qualityGateName: .quality_gate_name
              qualityGateStatus: .quality_gate_status
              qualityGateConditions: .quality_gate_conditions

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