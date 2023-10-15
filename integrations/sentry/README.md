# Sentry

Integration to import information from Sentry into Port.

The integration supports importing issues and projects from your Sentry account to Port, according to your mapping and definition.

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

## Deployment to Port

For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration in your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.config.sentryHost: Change the host to your Sentry host
# integration.config.sentryOrganization: Change the organization to your Sentry organization
# integration.secrets.sentryToken: Change the token to your Sentry token

helm upgrade --install my-sentry-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
	--set integration.identifier="my-sentry-integration"  \
	--set integration.type="sentry"  \
	--set integration.eventListener.type="POLLING"  \
	--set integration.config.sentryHost="https://sentry.io"  \
	--set integration.config.sentryOrganization="org-example"  \
	--set integration.secrets.sentryToken="<SENTRY_API_TOKEN>"  /
```

## Supported Kinds

### Project

The mapping should refer to one of the projects from the example response: [Sentry documentation](https://docs.sentry.io/api/projects/list-your-projects/)

<details>
<summary>blueprints.json</summary>

```json
{
  "identifier": "sentryProject",
  "title": "Project",
  "icon": "Sentry",
  "schema": {
    "properties": {
      "dateCreated": {
        "title": "dateCreated",
        "type": "string",
        "format": "date-time"
      },
      "platform": {
        "type": "string",
        "title": "platform"
      },
      "status": {
        "title": "status",
        "type": "string",
        "enum": [
          "active",
          "disabled",
          "pending_deletion",
          "deletion_in_progress"
        ]
      },
      "link": {
        "title": "link",
        "type": "string",
        "format": "url"
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
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
  - kind: project
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .slug
          title: .name
          blueprint: '"sentryProject"'
          properties:
            dateCreated: .dateCreated
            platform: .platform
            status: .status
            link: .organization.links.organizationUrl + "/projects/" + .name
```

</details>

### Issue

The mapping should refer to one of the issues in the example response: [Sentry documentation](https://docs.sentry.io/api/events/list-a-projects-issues/)

<details>
<summary>blueprints.json</summary>

```json
{
  "identifier": "sentryIssue",
  "title": "Issue",
  "icon": "Sentry",
  "schema": {
    "properties": {
      "link": {
        "title": "link",
        "type": "string",
        "format": "url"
      },
      "status": {
        "title": "status",
        "type": "string"
      },
      "isUnhandled": {
        "icon": "DefaultProperty",
        "title": "isUnhandled",
        "type": "boolean"
      }
    },
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {},
  "relations": {
    "project": {
      "title": "project",
      "target": "sentryProject",
      "required": false,
      "many": false
    }
  }
}
```

</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
 - kind: issue
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: ".id"
          title: ".title"
          blueprint: '"sentryIssue"'
          properties:
            link: ".permalink"
            status: ".status"
            isUnhandled: ".isUnhandled"
          relations:
            project: ".project.slug"
```

</details>

## Development

### Installation

```sh
make install
```

### Runnning Localhost

```sh
make run
```

or

```sh
ocean sail
```

### Running Tests

`make test`

### Access Swagger Documentation

> <http://localhost:8080/docs>

### Access Redoc Documentation

> <http://localhost:8080/redoc>

### Folder Structure

The Sentry integration suggested folder structure is as follows:

```
Sentry/
├─ main.py
├─ pyproject.toml
└─ Dockerfile
```
