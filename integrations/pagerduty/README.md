# pagerduty

Pagerduty integration for Port using Port-Ocean Framework

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

## Installation
For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration at your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.secrets.token: The Pagerduty API token
# integration.config.app_host: The Pagerduty app host
# integration.config.api_url: The Pagerduty api url. If not specified, the default will be https://api.pagerduty.com

helm upgrade --install my-pagerduty-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
	--set integration.identifier="my-pagerduty-integration"  \
	--set integration.type="pagerduty"  \
	--set integration.triggerChannel.type="POLLING"  \
	--set integration.secrets.token="token"  \
	--set integration.config.app_host="https://example.com"  \
    --set integration.config.api_url="https://api.pagerduty.com"  \
```
## Supported Kinds
### Services
The mapping should refer to one of the services in the example response: [Pagerduty documentation](https://developer.pagerduty.com/api-reference/e960cca205c0f-list-services)

<details>
<summary>blueprint.json</summary>

```json
{
   "identifier":"pagerdutyService",
   "description":"This blueprint represents a PagerDuty service in our software catalog",
   "title":"PagerDuty Service",
   "icon":"pagerduty",
   "schema":{
      "properties":{
         "status":{
            "title":"Status",
            "type":"string"
         }
      },
      "required":[
         
      ]
   },
   "mirrorProperties":{
      
   },
   "calculationProperties":{
      "service":{
         "title":"Service URL",
         "calculation":"'https://api.pagerduty.com/services/' + .identifier",
         "type":"string",
         "format":"url"
      }
   },
   "relations":{
      
   }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: services
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id
          title: .name
          blueprint: '"pagerdutyService"'
          properties:
            status: .status
```
</details>

### Incidents
The mapping should refer to one of the incidents in the example response: [Pagerduty documentation](https://developer.pagerduty.com/api-reference/9d0b4b12e36f9-list-incidents)

<details>
<summary>blueprint.json</summary>

```json
{
   "identifier":"pagerdutyIncident",
   "description":"This blueprint represents a PagerDuty incident in our software catalog",
   "title":"PagerDuty Incident",
   "icon":"pagerduty",
   "schema":{
      "properties":{
         "status":{
            "type":"string",
            "title":"Incident Status",
            "enum":[
               "triggered",
               "annotated",
               "acknowledged",
               "reassigned",
               "escalated",
               "reopened",
               "resolved"
            ]
         },
         "url":{
            "type":"string",
            "format":"url",
            "title":"Incident URL"
         },
         "urgency":{
            "type":"string",
            "title":"Incident Urgency",
            "enum":[
               "high",
               "low"
            ]
         },
         "responder":{
            "type":"string",
            "title":"Assignee"
         },
         "escalation_policy":{
            "type":"string",
            "title":"Escalation Policy"
         },
         "created_at":{
            "title":"Create At",
            "type":"string",
            "format":"date-time"
         },
         "updated_at":{
            "title":"Updated At",
            "type":"string",
            "format":"date-time"
         }
      },
      "required":[
         
      ]
   },
   "mirrorProperties":{},
   "calculationProperties":{},
   "relations":{
      "pagerdutyService":{
         "title":"PagerDuty Service",
         "target":"pagerdutyService",
         "required":false,
         "many":true
      }
   }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: incidents
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id | tostring
          title: .title
          blueprint: '"pagerdutyIncident"'
          properties:
            status: .status
            url: .self
            urgency: .urgency
            responder: .assignments[0].assignee.summary
            escalation_policy: .escalation_policy.summary
            created_at: .created_at
            updated_at: .updated_at
          relations:
            pagerdutyService: .service.id
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
The pagerduty integration suggested folder structure is as follows:

```
pagerduty/
├─ clients/             # The integration logic
│  ├─ pagerduty.py      # Wrapper to the Pagerduty REST API and other custom integration logic
├─ main.py              # The main exports the custom Ocean logic to the ocean sail command
├─ pyproject.toml
└─ Dockerfile
```