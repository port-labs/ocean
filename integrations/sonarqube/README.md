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
### Project
This kind represents a Sonarqube project.

<details>
<summary>blueprint.json</summary>

```json
{
	"identifier": "sonarqubeProject",
	"description": "This blueprint represents a Sonarqube project in our software catalog",
	"title": "SonarQube Project",
	"icon": "sonarqube",
	"schema": {
		"properties": {
			"organization": {
				"type": "string",
				"title": "Organization"
			},
			"visibility": {
				"type": "string",
				"title": "Visibility"
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
          blueprint: '"sonarqubeProject"'
          identifier: .key
          title: .name
          properties:
              organization: .organization
              visibility: .visibility
              tags: .tags

```
</details>

### Quality Gates
This kind represents a Sonarqube quality gate.

<details>
<summary>blueprint.json</summary>

```json
{
	"identifier": "sonarqubeQualityGate",
	"description": "This blueprint represents a Sonarqube quality gate in our software catalog",
	"title": "SonarQube Quality Gate",
	"icon": "sonarqube",
	"schema": {
		"properties": {
			"status": {
				"type": "string",
				"title": "Quality Gate Status",
				"enum": [
					"OK",
					"WARN",
					"ERROR",
					"NONE"
				],
				"enumColors": {
					"OK": "green",
					"WARN": "yellow",
					"ERROR": "red",
					"NONE": "lightGray"
				}
			},
			"conditions": {
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
  - kind: qualitygates
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          blueprint: '"sonarqubeQualityGate"'
          identifier: .id
          title: .name
          properties:
              status: .status
              conditions: .conditions

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