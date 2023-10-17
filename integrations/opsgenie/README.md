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
   "identifier":"opsGenieService",
   "description":"This blueprint represents an OpsGenie service in our software catalog",
   "title":"OpsGenie Service",
   "icon":"OpsGenie",
   "schema":{
      "properties":{
         "description":{
            "type":"string",
            "title":"Description",
            "icon":"DefaultProperty"
         },
         "url":{
            "title":"URL",
            "type":"string",
            "description":"URL to the service",
            "format":"url",
            "icon":"DefaultProperty"
         },
         "tags":{
            "type":"array",
            "items":{
               "type":"string"
            },
            "title":"Tags",
            "icon":"DefaultProperty"
         },
         "oncallTeam":{
            "type":"string",
            "title":"OnCall Team",
            "description":"Name of the team responsible for this service",
            "icon":"DefaultProperty"
         },
         "teamMembers":{
            "icon":"TwoUsers",
            "type":"array",
            "items":{
               "type":"string",
               "format":"user"
            },
            "title":"Team Members",
            "description":"Members of team responsible for this service"
         },
         "oncallUsers":{
            "icon":"TwoUsers",
            "type":"array",
            "items":{
               "type":"string",
               "format":"user"
            },
            "title":"Oncall Users",
            "description":"Who is on call for this service"
         },
         "numOpenIncidents":{
            "title":"Number of Open Incidents",
            "type":"number"
         }
      },
      "required":[]
   },
   "mirrorProperties":{},
   "calculationProperties":{
      "teamSize":{
         "title":"Team Size",
         "icon":"DefaultProperty",
         "description":"Size of the team",
         "calculation":".properties.teamMembers | length",
         "type":"number"
      }
   },
   "relations":{}
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
          identifier: .name | gsub("[^a-zA-Z0-9@_.:/=-]"; "-") | tostring
          title: .name
          blueprint: '"opsGenieService"'
          properties:
            description: .description
            url: .links.web
            tags: .tags
            oncallTeam: .__team.name
            teamMembers: '[.__team.members[].user.username]'
            oncallUsers: .__oncalls.onCallRecipients
            numOpenIncidents: '[ .__incidents[] | select(.status == "open")] | length'
```

</details>

### Alert

The mapping should refer to one of the alerts in the example response: [OpsGenie documentation](https://docs.opsgenie.com/docs/alert-api#list-alerts)

<details>
<summary>blueprint.json</summary>

```json
{
   "identifier":"opsGenieAlert",
   "description":"This blueprint represents an OpsGenie alert in our software catalog",
   "title":"OpsGenie Alert",
   "icon":"OpsGenie",
   "schema":{
      "properties":{
         "description":{
            "title":"Description",
            "type":"string"
         },
         "status":{
            "type":"string",
            "title":"Status",
            "enum":[
               "closed",
               "open"
            ],
            "enumColors":{
               "closed":"green",
               "open":"red"
            },
            "description":"The status of the alert"
         },
         "acknowledged":{
            "type":"boolean",
            "title":"Acknowledged"
         },
         "tags":{
            "type":"array",
            "items":{
               "type":"string"
            },
            "title":"Tags"
         },
         "responders":{
            "type":"array",
            "title":"Responders",
            "description":"Responders to the alert"
         },
         "integration":{
            "type":"string",
            "title":"Integration",
            "description":"The name of the Integration"
         },
         "priority":{
            "type":"string",
            "title":"Priority"
         },
         "sourceName":{
            "type":"string",
            "title":"Source Name",
            "description":"Alert source name"
         },
         "createdBy":{
            "title":"Created By",
            "type":"string",
            "format":"user"
         },
         "createdAt":{
            "title":"Create At",
            "type":"string",
            "format":"date-time"
         },
         "updatedAt":{
            "title":"Updated At",
            "type":"string",
            "format":"date-time"
         },
         "count":{
            "title":"Count",
            "type":"number"
         }
      },
      "required":[]
   },
   "mirrorProperties":{},
   "calculationProperties":{},
   "relations":{
      "relatedIncident":{
         "title":"Related Incident",
         "target":"opsGenieIncident",
         "required":false,
         "many":false
      }
   }
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
          relations:
            relatedIncident: .__relatedIncident.id
```

</details>

### Incident

The mapping should refer to one of the incidents in the example response: [OpsGenie documentation](https://docs.opsgenie.com/docs/incident-api#list-incidents)

<details>
<summary>blueprint.json</summary>

```json
{
   "identifier":"opsGenieIncident",
   "description":"This blueprint represents an OpsGenie incident in our software catalog",
   "title":"OpsGenie Incident",
   "icon":"OpsGenie",
   "schema":{
      "properties":{
         "description":{
            "title":"Description",
            "type":"string"
         },
         "status":{
            "type":"string",
            "title":"Status",
            "enum":[
               "closed",
               "open",
               "resolved"
            ],
            "enumColors":{
               "closed":"blue",
               "open":"red",
               "resolved":"green"
            },
            "description":"The status of the incident"
         },
         "url":{
            "type":"string",
            "format":"url",
            "title":"URL"
         },
         "tags":{
            "type":"array",
            "items":{
               "type":"string"
            },
            "title":"Tags"
         },
         "responders":{
            "type":"array",
            "title":"Responders",
            "description":"Responders to the alert"
         },
         "priority":{
            "type":"string",
            "title":"Priority"
         },
         "createdAt":{
            "title":"Create At",
            "type":"string",
            "format":"date-time"
         },
         "updatedAt":{
            "title":"Updated At",
            "type":"string",
            "format":"date-time"
         }
      },
      "required":[]
   },
   "mirrorProperties":{},
   "calculationProperties":{},
   "relations":{
      "services":{
         "title":"Impacted Services",
         "target":"opsGenieService",
         "many":true,
         "required":false
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
            services: '[.__impactedServices[] | .name | gsub("[^a-zA-Z0-9@_.:/=-]"; "-") | tostring]'
```

</details>

## Configuring real-time updates

Currently, the OpsGenie API lacks support for programmatic webhook creation. To set up a webhook configuration in OpsGenie for sending alert notifications to the Ocean integration, follow these steps:

### Prerequisite

Prepare a webhook `URL` using this format: `<app_host>/integration/webhook`. The `app_host` parameter should match the ingress where the integration will be deployed. For example, if your ingress exposes the OpsGenie Ocean integration at `https://myservice.domain.com`, your webhook `URL` should be `https://myservice.domain.com/integration/webhook`.

### Create a webhook in OpsGenie

1. Go to OpsGenie;
2. Select **Settings**;
3. Click on **Integrations** under the **Integrations** section of the sidebar;
4. Click on **Add integration**;
5. In the search box, type _Webhook_ and select the webhook option;
6. Input the following details:
   1. `Name` - use a meaningful name such as Port Ocean Webhook;
   2. Be sure to keep the "Enabled" checkbox checked;
   3. Check the "Add Alert Description to Payload" checkbox;
   4. Check the "Add Alert Details to Payload" checkbox;
   5. Add the following action triggers to the webhook by clicking on **Add new action**:
      1. If _alert is snoozed_ in Opsgenie, _post to url_ in Webhook;
      2. If _alert's description is updated_ in Opsgenie, _post to url_ in Webhook;
      3. If _alert's message is updated_ in Opsgenie, _post to url_ in Webhook;
      4. If _alert's priority is updated_ in Opsgenie, _post to url_ in Webhook;
      5. If _a responder is added to the alert_ in Opsgenie, _post to url_ in Webhook;
      6. if _a user executes "Assign Ownership_ in Opsgenie, _post to url_ in Webhook;
      7. if _a tag is added to the alert_ in Opsgenie, _post to url_ in Webhook;
      8. .if _a tag is removed from the alert_ in Opsgenie, _post to url_ in Webhook;
   6. `Webhook URL` - enter the value of the `URL` you created above.
7. Click **Save integration**

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