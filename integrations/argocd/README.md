# ArgoCD

ArgoCD integration for Port using Ocean Framework

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
  --set scheduledResyncInterval=60  \
	--set integration.identifier="my-argocd-integration"  \
	--set integration.type="argocd"  \
	--set integration.triggerChannel.type="POLLING"  \
	--set integration.secrets.token="<your-token>"  \
  --set integration.config.serverUrl="<your-server-url>"  \
```

### Generating ArgoCD token
1. Navigate to `<serverURL>/settings/accounts/<user>`. For example, if you access your ArgoCD at `https://localhost:8080/`, you should navigate to `https://localhost:8080/settings/accounts/<user>`.
2. Under **Tokens**, Click **Generate New** to create a new token.


## Supported Kinds

### Cluster
This kind represents an ArgoCD cluster. The mapping should refer to one of the cluster schema from the [ArgoCD documentation](https://cd.apps.argoproj.io/swagger-ui#operation/ClusterService_List)

<details>
<summary>blueprint.json</summary>

```json
{
      "identifier": "argocdCluster",
      "description": "This blueprint represents an ArgoCD cluster",
      "title": "ArgoCD Cluster",
      "icon": "Argo",
      "schema": {
          "properties": {
              "namespaces": {
                  "items": {
                      "type": "string"
                  },
                  "icon": "DefaultProperty",
                  "title": "Namespace",
                  "type": "array",
                  "description": "Holds list of namespaces which are accessible in that cluster."
              },
              "applicationsCount": {
                  "title": "Applications Count",
                  "type": "number",
                  "description": "The number of applications managed by Argo CD on the cluster",
                  "icon": "DefaultProperty"
              },
              "serverVersion": {
                  "title": "Server Version",
                  "type": "string",
                  "description": "Contains information about the Kubernetes version of the cluster",
                  "icon": "DefaultProperty"
              },
              "labels": {
                  "title": "Labels",
                  "type": "object",
                  "description": "Contains information about cluster metadata",
                  "icon": "DefaultProperty"
              },
              "updatedAt": {
                  "icon": "DefaultProperty",
                  "title": "Updated At",
                  "type": "string",
                  "format": "date-time"
              },
              "server": {
                  "title": "Server",
                  "description": "The API server URL of the Kubernetes cluster",
                  "type": "string",
                  "format": "url",
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
  - kind: cluster
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .name
          title: .name
          blueprint: '"argocdCluster"'
          properties:
            namespaces: .namespaces
            applicationsCount: .info.applicationsCount
            serverVersion: .serverVersion
            labels: .labels
            updatedAt: .connectionState.attemptedAt
            server: .server
```
</details>


### Projects
This kind represents an ArgoCD project. The mapping should refer to one of the projects schema from the [ArgoCD documentation](https://cd.apps.argoproj.io/swagger-ui#operation/ProjectService_List)

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
                  "type": "string",
                  "icon": "DefaultProperty"
              },
              "createdAt": {
                  "title": "Created At",
                  "type": "string",
                  "format": "date-time",
                  "icon": "DefaultProperty"
              },
              "description": {
                  "title": "Description",
                  "description": "Project description",
                  "type": "string",
                  "icon": "DefaultProperty"
              }
          },
          "required": []
      },
      "mirrorProperties": {},
      "calculationProperties": {},
      "relations": {
          "cluster": {
              "title": "Cluster",
              "target": "argocdCluster",
              "required": false,
              "many": true
          }
      }
}
```
</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
resources:
  - kind: project
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
            description: .spec.description
          relations:
            cluster: '[.spec.destinations[].name | select(test("^[a-zA-Z0-9@_.:/=-]+$"))]'
```
</details>


### Applications
This kind represents an ArgoCD application. The mapping should refer to one of the applications schema from the [ArgoCD documentation](https://cd.apps.argoproj.io/swagger-ui#operation/ApplicationService_List)

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
  - kind: application
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


## Configuring real-time updates

In this example, you are going to configure ArgoCD to send real-time updates to Ocean

### Prerequisite

1. You have access to a Kubernetes cluster where ArgoCD is deployed.
2. You have `kubectl` installed and configured to access your cluster.


### Steps

1. Install ArgoCD notifications manifest;

```bash
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj-labs/argocd-notifications/release-1.0/manifests/install.yaml
```

2. Install ArgoCD triggers and templates manifest;
```bash
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj-labs/argocd-notifications/release-1.0/catalog/install.yaml
```

3. Use `kubectl` to connect to the Kubernetes cluster where your ArgoCD instance is deployed;

```bash
kubectl config use-context <your-cluster-context>
```

4. Set the current namespace to your ArgoCD namespace, use the following command;

```bash
kubectl config set-context --current --namespace=<your-namespace>
```

5. Create a YAML file (e.g. `argocd-webhook-config.yaml`) that configures the webhook notification service. The example below shows how to set up a webhook to send real-time events whenever ArgoCD applications are updated. The YAML file includes the following components:

    1. Notification service definition;
    2. Template for the webhook message body;
    3. Trigger definitions;
    4. Subscriptions to the notifications.

Here's an example YAML. Make sure to replace `https://port-ocean-service-url.com` with the actual URL of the ingress or service where the ocean integration will be deployed. By default, incoming webhook events are sent to `/integration/webhook` path in Ocean so do not replace the path parameter.

```yaml showLineNumbers
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-notifications-cm
data:
  trigger.on-sync-operation-change: |
    - description: Application syncing has updated
      send:
      - app-status-change
      when: app.status.operationState.phase in ['Error', 'Failed', 'Succeeded', 'Running']
  trigger.on-deployed: |
    - description: Application is synced and healthy
      send:
      - app-status-change
      when: app.status.operationState.phase in ['Succeeded'] and app.status.health.status == 'Healthy'
  trigger.on-health-degraded: |
    - description: Application has degraded
      send:
      - app-status-change
      when: app.status.health.status == 'Degraded'
  service.webhook.port-ocean: |
    url: https://port-ocean-service-url.com
    headers:
    - name: Content-Type
      value: application/json
  template.app-status-change: |
    webhook:
      port-ocean:
        method: POST
        path: /integration/webhook
        body: |
          {
            "action": "upsert",
            "application_name": "{{.app.metadata.name}}"
          }
  subscriptions: |
    - recipients:
      - port-ocean
      triggers:
      - on-deployed
      - on-health-degraded
      - on-sync-operation-change
```

6. Use `kubectl` to apply the YAML file to your cluster. Run the following command, replacing <your-namespace> with your ArgoCD namespace and <path-to-yaml-file> with the actual path to your YAML file:

```bash
kubectl apply -n <your-namespace> -f <path-to-yaml-file>
```

This command deploys the webhook notification configuration to your ArgoCD notification configmap (`argocd-notifications-cm`), allowing Ocean to receive real-time events.

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