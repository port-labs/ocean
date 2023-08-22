# ArgoCD

ArgoCD projects, applications and deployment resources integration for Port using Port-Ocean Framework

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

## Installation
For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration at your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.secrets.token: Your ArgoCD API token
# integration.config.serverUrl: The url of your ArgoCD server

helm upgrade --install my-argocd-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
	--set integration.identifier="my-argocd-integration"  \
	--set integration.type="argocd"  \
	--set integration.triggerChannel.type="POLLING"  \
	--set integration.secrets.token="<your-token>"  \
    --set integration.config.serverUrl="<your-server-url>"  \
     --set ingress.enabled=true  \
     --set ingress.annotations."nginx\.ingress\.kubernetes\.io/rewrite-target"= / 
```
## Supported Kinds
### Projects
This kind represents an ArgoCD project. The mapping should refer to one of the projects from the example response [ArgoCD documentation](https://cd.apps.argoproj.io/swagger-ui#operation/ProjectService_List)

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier": "argocdProject",
    "description": "This blueprint represents an ArgoCD Project",
    "title": "ArgoCD Project",
    "icon": "Argo",
    "schema": {
        "properties": {
        "namespace": {
            "title": "Namespace",
            "type": "string"
        },
        "createdAt": {
            "title": "creation At",
            "type": "string",
            "format": "date-time"
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
      query: "true"
    port:
      entity:
        mappings:
          identifier: .metadata.name
          title: .metadata.name
          blueprint: '"argocdProject"'
          properties:
            namespace: .metadata.namespace
            createdAt: .metadata.creationTimestamp

```
</details>

### Applications
This kind represents an ArgoCD application. The mapping should refer to one of the applications from the example response [ArgoCD documentation](https://cd.apps.argoproj.io/swagger-ui#operation/ApplicationService_List)

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier": "argocdApplication",
    "description": "This blueprint represents an ArgoCD Application",
    "title": "ArgoCD Application",
    "icon": "Argo",
    "schema": {
        "properties": {
        "gitRepo": {
            "type": "string",
            "format": "url",
            "icon": "Git",
            "title": "Repository URL",
            "description": "The URL of the Git repository containing the application source code"
        },
        "gitPath": {
            "type": "string",
            "title": "Path",
            "description": "The path within the Git repository where the application manifests are located"
        },
        "sourceType": {
            "type": "string",
            "title": "Source Type"
        },
        "destinationServer": {
            "type": "string",
            "title": "Destination Server",
            "format": "url"
        },
        "namespace": {
            "type": "string",
            "title": "Namespace"
        },
        "syncStatus": {
            "type": "string",
            "title": "Sync Status",
            "enum": [
            "Synced",
            "OutOfSync",
            "Unknown"
            ],
            "enumColors": {
            "Synced": "green",
            "OutOfSync": "red",
            "Unknown": "lightGray"
            },
            "description": "The sync status of the application"
        },
        "healthStatus": {
            "type": "string",
            "title": "Health Status",
            "enum": [
            "Healthy",
            "Missing",
            "Suspended",
            "Degraded",
            "Progressing",
            "Unknown"
            ],
            "enumColors": {
            "Healthy": "green",
            "Missing": "yellow",
            "Suspended": "purple",
            "Degraded": "red",
            "Progressing": "blue",
            "Unknown": "lightGray"
            },
            "description": "The health status of the application"
        },
        "createdAt": {
            "title": "Created At",
            "type": "string",
            "format": "date-time"
        }
        },
        "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
        "project": {
        "title": "Project",
        "target": "argocdProject",
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
resources:
  - kind: applications
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .metadata.uid
          title: .metadata.name
          blueprint: '"argocdApplication"'
          properties:
            gitRepo: .spec.source.repoURL
            gitPath: .spec.source.path
            sourceType: .status.sourceType
            destinationServer: .spec.destination.server
            namespace: .metadata.namespace
            syncStatus: .status.sync.status
            healthStatus: .status.health.status
            createdAt: .metadata.creationTimestamp
          relations:
            project: .spec.project

```
</details>

### Deployment
This kind represents all the different deployment resources. It includes Deployment, Services, Ingress etc. The mapping should refer to one of the applications from the example response [ArgoCD documentation](https://cd.apps.argoproj.io/swagger-ui#operation/ApplicationService_List)

<details>
<summary>blueprint.json</summary>

```json
{
    "identifier": "argocdDeployment",
    "description": "This blueprint represents an ArgoCD Deployment",
    "title": "ArgoCD Deployment",
    "icon": "Argo",
    "schema": {
        "properties": {
        "kind": {
            "type": "string",
            "title": "Resource Kind"
        },
        "syncStatus": {
            "type": "string",
            "title": "Sync Status",
            "enum": [
            "Synced",
            "OutOfSync",
            "Unknown"
            ],
            "enumColors": {
            "Synced": "green",
            "OutOfSync": "red",
            "Unknown": "lightGray"
            },
            "description": "The sync status of the application"
        },
        "healthStatus": {
            "type": "string",
            "title": "Health Status",
            "enum": [
            "Healthy",
            "Missing",
            "Suspended",
            "Degraded",
            "Progressing",
            "Unknown"
            ],
            "enumColors": {
            "Healthy": "green",
            "Missing": "yellow",
            "Suspended": "purple",
            "Degraded": "red",
            "Progressing": "blue",
            "Unknown": "lightGray"
            },
            "description": "The health status of the application"
        },
        "group": {
            "type": "string",
            "title": "Group"
        },
        "version": {
            "title": "Version",
            "type": "string"
        },
        "namespace": {
            "type": "string",
            "title": "Namespace"
        }
        },
        "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
        "application": {
        "title": "Application",
        "target": "argocdApplication",
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
resources:
  - kind: deployments
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .name
          title: .name
          blueprint: '"argocdDeployment"'
          properties:
            kind: .kind
            syncStatus: .status
            healthStatus: .health.status
            group: .group
            version: .version
            namespace: .namespace
          relations:
            application: .application_uid

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
The ArgoCD integration suggested folder structure is as follows:

```
argocd/
├─ argocd_integration/             # The integration logic
│  ├─ client.py      # Wrapper to the ArgoCD REST API and other custom integration logic
├─ main.py              # The main exports the custom Ocean logic to the ocean sail command
├─ pyproject.toml
└─ Dockerfile
```