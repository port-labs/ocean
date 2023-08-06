# New Relic

New Relic Integration for Port using Port-Ocean Framework

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

## Installation
For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration at your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.config.newRelicAPIKey: The New Relic API Key of type [User key](https://docs.newrelic.com/docs/apis/intro-apis/new-relic-api-keys/#user-key)
# integration.config.newRelicAccountID: The New Relic Account ID of type [Account ID](https://docs.newrelic.com/docs/apis/intro-apis/new-relic-api-keys/#account-id)
# integration.config.newRelicGraphqlURL: Default value is https://api.newrelic.com/graphql if you are using a EU data center change the value to EU data center: https://api.eu.newrelic.com/graphql
# ingress.annotations."nginx\.ingress\.kubernetes\.io/rewrite-target": Change the annotation value and key to match your ingress controller

helm upgrade --install my-ocean-integration port-labs/port-ocean \
  --namespace port-ocean \
  --set port.clientId="<CLIENT_ID>" \
  --set port.clientSecret="<CLIENT_SECRET>" \
  --set initializePortResources=true \
  --set integration.identifier="<INTEGRATION_IDENTIFIER>" \
  --set integration.type="newrelic" \
  --set integration.eventListener.type="POLLING" \
  --set integration.config.newRelicAPIKey="<newRelicAPIKey>" \
  --set integration.config.newRelicAccountID="<newRelicAccountID>" \
  --set ingress.enabled=true  \
  --set ingress.annotations."nginx\.ingress\.kubernetes\.io/rewrite-target"= / 
```

## How it works

There are two important concepts in New Relic that we need to understand to use the integration:

- *Entity* - An entity is a host, an application, a service, a database, or any other component that sends data to New Relic. 
Entities are identified by a unique GUID. [For more information](https://docs.newrelic.com/docs/new-relic-solutions/new-relic-one/core-concepts/what-entity-new-relic/)
- *Issues* - Issues are groups of incidents that describe the underlying problem of your symptoms.
When a new incident is created, incident intelligence opens an issue and evaluates other open issues for correlations. An issue will contain arrays of all the tags (metadata) from all the incidents it contains. [For more information](https://docs.newrelic.com/docs/alerts-applied-intelligence/new-relic-alerts/get-started/alerts-ai-overview-page/#issues)

The integration runs in two modes:
- **Resync** - The integration will fetch all the entities and issues from New Relic and will create the corresponding entities and issues in Port.
There integration will resync once it detects a change in the integration config.
  - *POLLING* (default) it pulls the configuration from port every minute and checks for changes, if there is a change it will resync.
  - *KAFKA* it listens to a kafka topic for changes in the configuration, if there is a change it will resync.
- **On event** - NewRelic supports configuring [workflows](https://docs.newrelic.com/docs/alerts-applied-intelligence/applied-intelligence/incident-workflows/incident-workflows/#workflows-triggered) that will trigger a webhook when a change to issues that the policies are monitoring occurs. The integration will listen to those webhooks and will update the corresponding issues in Port.


### The integration configuration

The integration configuration is how you specify the exact resources you want to query from your NewRelic, and also how you specify which entities and which properties you want to fill with data from NewRelic.

This logic will be defined in the integration app config.

### Entities  
So as we can understand, entity could eventually be any type of resource and so that the integration will be able to map each type of resource to a 
corresponding blueprint in port we need to provide the integration with instruction on how to handle each kind.

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier": "newRelicService",
    "description": "This blueprint represents a New Relic service or application in our software catalog",
    "title": "New Relic Service",
    "icon": "NewRelic",
    "schema": {
      "properties": {
        "has_apm": {
          "title": "Has APM",
          "type": "boolean"
        },
        "open_issues_count": {
          "title": "Open Issues Count",
          "type": "number",
          "default": 0
        },
        "link": {
          "title": "Link",
          "type": "string",
          "format": "url"
        },
        "reporting": {
          "title": "Reporting",
          "type": "boolean"
        },
        "tags": {
          "title": "Tags",
          "type": "object"
        },
        "account_id": {
          "title": "Account ID",
          "type": "string"
        },
        "type": {
          "title": "Type",
          "type": "string"
        },
        "domain": {
          "title": "Domain",
          "type": "string"
        },
        "throughput": {
          "title": "Throughput",
          "type": "number"
        },
        "response_time_avg": {
          "title": "Response Time AVG",
          "type": "number"
        },
        "error_rate": {
          "title": "Error Rate",
          "type": "number"
        },
        "instance_count": {
            "title": "Instance Count",
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

Let's take a look at the following example:
<details>
<summary>port-app-config.yaml</summary>

```yaml
  - kind: newRelicService
    selector:
      query: 'true'
      newRelicTypes: ['SERVICE', 'APPLICATION']
      calculateOpenIssueCount: true
      entityQueryFilter: "type in ('SERVICE','APPLICATION')"
      entityExtraPropertiesQuery: |
        ... on ApmApplicationEntityOutline {
          guid
          name
          alertSeverity
          applicationId
          apmBrowserSummary {
            ajaxRequestThroughput
            ajaxResponseTimeAverage
            jsErrorRate
            pageLoadThroughput
            pageLoadTimeAverage
          }
          apmSummary {
            apdexScore
            errorRate
            hostCount
            instanceCount
            nonWebResponseTimeAverage
            nonWebThroughput
            responseTimeAverage
            throughput
            webResponseTimeAverage
            webThroughput
          }
        }
    port:
      entity:
        mappings:
          blueprint: '"newRelicService"'
          identifier: .guid
          title: .name
          properties:
            has_apm: 'if .domain | contains("APM") then "true" else "false" end'
            link: .permalink
            open_issues_count: .open_issues_count
            reporting: .reporting
            tags: .tags
            domain: .domain
            type: .type
```
</details>

#### Selector
- **query** - A query to filter the entities that will be fetched from New Relic. Default value is `true` which means that all entities will be fetched.
- **newRelicTypes** - An array of New Relic entity types that will be fetched. Default value is `['SERVICE', 'APPLICATION']`. This is related to the `type` field in the New Relic entity.
- **calculateOpenIssueCount** - 
  - A boolean value that indicates if the integration should calculate the number of open issues for each entity. Default value is `false`. Here we override the default value to `true` because we want to calculate the number of open issues for each service entity.
  - **Note** - This can cause a performance degradation as it will have to calculate the number of open issues for each entity which unfortunately is not supported by New Relic API and so the integration will have to fetch all the issues and then calculate the number of open issues for each entity.
- **entityQueryFilter** - 
  - A filter that will be applied to the New Relic API query. This will be places inside the `query` field of the `entitySearch` query in the New Relic GraphQL API. For examples of query filters see [here](https://docs.newrelic.com/docs/apis/nerdgraph/examples/nerdgraph-entities-api-tutorial/#search-query)
  - **Note** - Not specifying this field will cause the integration to fetch all the entities and map them to the blueprint defined in the kind.
  - **Rule of thumb** - Most of the time the EntityQueryFilter will be the same as the NewRelicTypes. For example, if we want to fetch all the services and applications we will set the EntityQueryFilter to `type in ('SERVICE','APPLICATION')` and the NewRelicTypes to `['SERVICE', 'APPLICATION']`.
- **entityExtraPropertiesQuery** -
  - An optional property that allows defining extra properties to fetch for each New Relic Entity. This will be concatenated with the default query properties we are requesting under the `entities` section in `entitySearch` query in the New Relic GraphQL API. For examples of additional query properties [here](https://docs.newrelic.com/docs/apis/nerdgraph/examples/nerdgraph-entities-api-tutorial/#apm-summary)

#### Port
- Under the `port` field we define the mapping between the New Relic entity and the Port entity.
- The port, entity and the mappings keys used to map the NewRelic API object fields to Port entities.

### Issues
Unlike entities, where entities can be any type of resource and can be mapped to any type of blueprint, issues are always mapped to only one blueprint.

That issue blueprint can have relations to all other entities blueprints.

<details>
<summary>blueprint.json</summary>

```json
{
  "identifier": "newRelicAlert",
  "description": "This blueprint represents a New Relic alert in our software catalog",
  "title": "New Relic Alert",
  "icon": "NewRelic",
  "schema": {
    "properties": {
      "priority": {
        "type": "string",
        "title": "Priority",
        "enum": [
          "CRITICAL",
          "HIGH",
          "MEDIUM",
          "LOW"
        ],
        "enumColors": {
          "CRITICAL": "red",
          "HIGH": "red",
          "MEDIUM": "yellow",
          "LOW": "green"
        }
      },
      "state": {
        "type": "string",
        "title": "State",
        "enum": [
          "ACTIVATED",
          "CLOSED",
          "CREATED"
        ],
        "enumColors": {
          "ACTIVATED": "yellow",
          "CLOSED": "green",
          "CREATED": "lightGray"
        }
      },
      "trigger": {
        "type": "string",
        "title": "Trigger"
      },
      "sources": {
        "type": "array",
        "title": "Sources"
      },
      "alertPolicyNames": {
        "type": "array",
        "title": "Alert Policy Names"
      },
      "conditionName": {
        "type": "array",
        "title": "Condition Name"
      },
      "activatedAt": {
        "type": "string",
        "title": "Time Issue was activated"
      }
    },
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {},
  "relations": {
    "newRelicService": {
      "title": "New Relic Service",
      "target": "newRelicService",
      "required": false,
      "many": true
    }
  }
}
```
</details>


Let's take a look at a configuration example for issues:
<details>
<summary>port-app-config.yaml</summary>

```yaml
  - kind: newRelicAlert
    selector:
      query: 'true'
      newRelicTypes: ['ISSUE']
    port:
      entity:
        mappings:
          blueprint: '"newRelicAlert"'
          identifier: .issueId
          title: .title[0]
          properties:
              priority: .priority
              state: .state
              sources: .sources
              conditionName: .conditionName
              alertPolicyNames: .policyName
              activatedAt: .activatedAt
          relations:
              newRelicService: .APPLICATION.entity_guids + .SERVICE.entity_guids
```
</details>

#### Selector
- **query** - A query to filter the issues that will be fetched from New Relic. Default value is `true` which means that all issues will be fetched.
- **newRelicTypes** - An array of New Relic entity types that will be fetched. The `ISSUE` type allows the integration to resolve from the configuration file which kind refers to the NewRelic Issues.

#### Port
- Under the `port` field we define the mapping between the New Relic issue and the Port issue.
- The port, entity and the mappings keys used to map the NewRelic API object fields to Port entities.
- The relations key is used to map the NewRelic API object fields to Port entities relations.
  - **Note** - The relations key is optional and can be omitted if the issue blueprint doesn't have any relations.
    - To support dynamic relations to any type of blueprint created from a NewRelic entity, we are adding to the issue entity a key per entity type (e.g. APPLICATION) and inside of it we are adding a list of all the entity guids that are related to the issue.

### Listening to New Relic events
The integration supports listening to New Relic events and updating the corresponding issues in Port.
Required configuration:

#### Installation
The following arguments needs to be set in the helm chart values so that the integration will be accessible from New Relic
- `ingress.enabled=true`
- `ingress.annotations."nginx\.ingress\.kubernetes\.io/rewrite-target"= /`

#### New Relic
- Create a workflow in New Relic that will send the events to the integration endpoint.
  - the url should be `https://<INTEGRATION_URL>/integration/events`
- The notification message must contain the following properties:
```
{
    "issueId": {{ json issueId }},
    "title": {{ json annotations.title }},
    "state": {{ json state }},
    "entityGuids": {{ json entitiesData.ids }},
}
```
if you wish to add more properties to the notification message you can do so by adding them to the notification message and then mapping them in the integration app config.


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