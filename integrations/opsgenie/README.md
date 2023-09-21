# OpsGenie

OpsGenie Integration powered by Port Ocean


## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

## Installation
For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration at your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.secrets.apiToken: The OpsGenie API token
# integration.config.apiUrl: The OpsGenie api url. If not specified, the default will be https://api.opsgenie.com. If you are using the EU instance of Opsgenie, the apiURL needs to be https://api.eu.opsgenie.com for requests to be executed.

helm upgrade --install my-opsgenie-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
	--set integration.identifier="my-opsgenie-integration"  \
	--set integration.type="opsgenie"  \
	--set integration.triggerChannel.type="POLLING"  \
	--set integration.secrets.apiToken="token"  \
  --set integration.config.apiUrl="https://api.opsgenie.com"
```
## Supported Kinds
### Service
The mapping should refer to one of the services in the example response: [OpsGenie documentation](https://docs.opsgenie.com/docs/service-api)

<details>
<summary>blueprint.json</summary>

```json
{
	"identifier": "opsGenieService",
	"description": "This blueprint represents an OpsGenie service in our software catalog",
	"title": "OpsGenie Service",
	"icon": "OpsGenie",
	"schema": {
		"properties": {
			"description": {
				"type": "string",
				"title": "Description",
				"icon": "DefaultProperty"
			},
			"url": {
				"title": "URL",
				"type": "string",
				"description": "URL to the service",
				"format": "url"
			},
			"tags": {
				"type": "array",
				"items": {
					"type": "string"
				},
				"title": "Tags",
				"icon": "DefaultProperty"
			},
			"oncallTeam": {
				"type": "string",
				"title": "OnCall Team",
				"description": "Name of the team responsible for this service",
				"icon": "DefaultProperty"
			},
			"teamMembers": {
				"icon": "TwoUsers",
				"type": "array",
				"items": {
					"type": "string",
					"format": "user"
				},
				"title": "Team Members",
				"description": "Members of team responsible for this service"
			},
			"teamSize": {
				"type": "number",
				"title": "Team Size",
				"description": "Size of the team",
				"icon": "DefaultProperty"
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
  - kind: service
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id
          title: .name
          blueprint: '"opsGenieService"'
          properties:
            description: .description
            url: .links.web
            tags: .tags
            oncallTeam: .__team.name
            teamMembers: '[.__team.members[].user.username]'
            teamSize: .__team.members | length
```
</details>

### Alert
The mapping should refer to one of the alerts in the example response: [OpsGenie documentation](https://docs.opsgenie.com/docs/alert-api#list-alerts)

<details>
<summary>blueprint.json</summary>

```json
{
	"identifier": "opsGenieAlert",
	"description": "This blueprint represents an OpsGenie alert in our software catalog",
	"title": "OpsGenie Alert",
	"icon": "OpsGenie",
	"schema": {
		"properties": {
			"description": {
				"title": "Description",
				"type": "string"
			},
			"status": {
				"type": "string",
				"title": "Status",
				"enum": [
					"closed",
					"open"
				],
				"enumColors": {
					"closed": "green",
					"open": "red"
				},
				"description": "The status of the alert"
			},
			"acknowledged": {
				"type": "boolean",
				"title": "Acknowledged"
			},
			"tags": {
				"type": "array",
				"items": {
					"type": "string"
				},
				"title": "Tags"
			},
			"responders": {
				"type": "array",
				"title": "Responders",
				"description": "Responders to the alert"
			},
			"integration": {
				"type": "string",
				"title": "Integration",
				"description": "The name of the Integration"
			},
			"priority": {
				"type": "string",
				"title": "Priority"
			},
			"sourceName": {
				"type": "string",
				"title": "Source Name",
				"description": "Alert source name"
			},
			"createdBy": {
				"title": "Created By",
				"type": "string",
				"format": "user"
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
			"count": {
				"title": "Count",
				"type": "number"
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
  - kind: alert
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id
          title: .message
          blueprint: '"opsGenieAlert"'
          properties:
            status: .status
            acknowledged: .acknowledged
            responders: .responders
            priority: .priority
            sourceName: .source
            tags: .tags
            count: .count
            createdBy: .owner
            createdAt: .createdAt
            updatedAt: .updatedAt
            description: .description
            integration: .integration.name
```
</details>

### Incident
The mapping should refer to one of the incidents in the example response: [OpsGenie documentation](https://docs.opsgenie.com/docs/incident-api#list-incidents)

<details>
<summary>blueprint.json</summary>

```json
{
	"identifier": "opsGenieIncident",
	"description": "This blueprint represents an OpsGenie incident in our software catalog",
	"title": "OpsGenie Incident",
	"icon": "OpsGenie",
	"schema": {
		"properties": {
			"description": {
				"title": "Description",
				"type": "string"
			},
			"status": {
				"type": "string",
				"title": "Status",
				"enum": [
					"closed",
					"open",
					"resolved"
				],
				"enumColors": {
					"closed": "blue",
					"open": "red",
					"resolved": "green"
				},
				"description": "The status of the incident"
			},
			"url": {
				"type": "string",
				"format": "url",
				"title": "URL"
			},
			"tags": {
				"type": "array",
				"items": {
					"type": "string"
				},
				"title": "Tags"
			},
			"responders": {
				"type": "array",
				"title": "Responders",
				"description": "Responders to the alert"
			},
			"priority": {
				"type": "string",
				"title": "Priority"
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
			}
		},
		"required": []
	},
	"mirrorProperties": {},
	"calculationProperties": {},
	"relations": {
		"services": {
			"title": "Impacted Services",
			"target": "opsGenieService",
			"many": true,
			"required": false
		}
	}
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: incident
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id
          title: .message
          blueprint: '"opsGenieIncident"'
          properties:
            status: .status
            responders: .responders
            priority: .priority
            tags: .tags
            url: .links.web
            createdAt: .createdAt
            updatedAt: .updatedAt
            description: .description
          relations:
            services: .impactedServices
```
</details>

## Webhook Configuration
The OpsGenie API currently does not offer support for programmatically creating webhooks. To implement a webhook with this ocean integration, users are kindly requested to configure it manually within [OpsGenie's interface](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/webhook/examples/opsgenie#create-a-webhook-in-opsgenie). Ensure that you use the following URL format when configuring the webhook: `<your_app_host>/integration/webhook`.

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
The opsgenie integration suggested folder structure is as follows:

```
opsgenie/
│  ├─ client.py      # Wrapper to the OpsGenie REST API and other custom integration logic
├─ main.py              # The main exports the custom Ocean logic to the ocean sail command
├─ pyproject.toml
└─ Dockerfile
```