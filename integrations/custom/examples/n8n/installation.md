# n8n Integration Installation Examples

This example demonstrates how to set up the Ocean Custom integration with n8n using cursor pagination and API key authentication.

## Prerequisites

1. Port credentials (`CLIENT_ID` and `CLIENT_SECRET`)
2. n8n instance URL (e.g., `https://your-instance.com/api`)
3. n8n API key (see [n8n API docs](https://docs.n8n.io/api/authentication/))

## Docker

```bash
docker run -i --rm --platform=linux/amd64 \
  -e OCEAN__EVENT_LISTENER='{"type":"ONCE"}' \
  -e OCEAN__INITIALIZE_PORT_RESOURCES=true \
  -e OCEAN__SEND_RAW_DATA_EXAMPLES=true \
  -e OCEAN__INTEGRATION__IDENTIFIER=n8n-integration \
  -e OCEAN__INTEGRATION__CONFIG__BASE_URL="https://your-instance.com/api" \
  -e OCEAN__INTEGRATION__CONFIG__AUTH_TYPE="api_key" \
  -e OCEAN__INTEGRATION__CONFIG__API_KEY_HEADER="X-N8N-API-KEY" \
  -e OCEAN__INTEGRATION__CONFIG__API_KEY="<ENTER N8N API KEY>" \
  -e OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE="cursor" \
  -e OCEAN__INTEGRATION__CONFIG__PAGINATION_PARAM="cursor" \
  -e OCEAN__INTEGRATION__CONFIG__SIZE_PARAM="limit" \
  -e OCEAN__INTEGRATION__CONFIG__PAGE_SIZE="100" \
  -e OCEAN__INTEGRATION__CONFIG__CURSOR_PATH="nextCursor" \
  -e OCEAN__INTEGRATION__CONFIG__HAS_MORE_PATH="nextCursor" \
  -e OCEAN__PORT__CLIENT_ID="<ENTER PORT CLIENT ID>" \
  -e OCEAN__PORT__CLIENT_SECRET="<ENTER PORT CLIENT SECRET>" \
  -e OCEAN__PORT__BASE_URL="https://api.getport.io" \
  ghcr.io/port-labs/port-ocean-custom:latest
```

## Helm

```bash
helm repo add port-labs https://port-labs.github.io/helm-charts
helm repo update

helm install n8n-integration port-labs/port-ocean-custom \
  --set eventListener.type=ONCE \
  --set initializePortResources=true \
  --set sendRawDataExamples=true \
  --set integration.identifier=n8n-integration \
  --set integration.config.baseUrl=https://your-instance.com/api \
  --set integration.config.authType=api_key \
  --set integration.config.apiKeyHeader=X-N8N-API-KEY \
  --set integration.secrets.apiKey=<ENTER N8N API KEY> \
  --set integration.config.paginationType=cursor \
  --set integration.config.paginationParam=cursor \
  --set integration.config.sizeParam=limit \
  --set integration.config.pageSize=100 \
  --set integration.config.cursorPath=nextCursor \
  --set integration.config.hasMorePath=nextCursor \
  --set port.clientId=<ENTER PORT CLIENT ID> \
  --set port.clientSecret=<ENTER PORT CLIENT SECRET> \
  --set port.baseUrl=https://api.getport.io
```

### Using values.yaml

Create a `n8n-values.yaml` file:

```yaml
port:
  clientId: <ENTER PORT CLIENT ID>
  clientSecret: <ENTER PORT CLIENT SECRET>
  baseUrl: https://api.getport.io

integration:
  identifier: n8n-integration
  config:
    baseUrl: https://your-instance.com/api
    authType: api_key
    apiKeyHeader: X-N8N-API-KEY
    paginationType: cursor
    paginationParam: cursor
    sizeParam: limit
    pageSize: 100
    cursorPath: nextCursor
    hasMorePath: nextCursor
  secrets:
    apiKey: <ENTER N8N API KEY>

initializePortResources: true
sendRawDataExamples: true
eventListener:
  type: ONCE
```

Then install:

```bash
helm install n8n-integration port-labs/port-ocean-custom -f n8n-values.yaml
```

## Kubernetes

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: n8n-integration-secrets
type: Opaque
stringData:
  OCEAN__PORT__CLIENT_ID: <ENTER PORT CLIENT ID>
  OCEAN__PORT__CLIENT_SECRET: <ENTER PORT CLIENT SECRET>
  OCEAN__INTEGRATION__CONFIG__API_KEY: <ENTER N8N API KEY>
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: n8n-integration-config
data:
  OCEAN__INTEGRATION__IDENTIFIER: n8n-integration
  OCEAN__INTEGRATION__CONFIG__BASE_URL: https://your-instance.com/api
  OCEAN__INTEGRATION__CONFIG__AUTH_TYPE: api_key
  OCEAN__INTEGRATION__CONFIG__API_KEY_HEADER: X-N8N-API-KEY
  OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE: cursor
  OCEAN__INTEGRATION__CONFIG__PAGINATION_PARAM: cursor
  OCEAN__INTEGRATION__CONFIG__SIZE_PARAM: limit
  OCEAN__INTEGRATION__CONFIG__PAGE_SIZE: "100"
  OCEAN__INTEGRATION__CONFIG__CURSOR_PATH: nextCursor
  OCEAN__INTEGRATION__CONFIG__HAS_MORE_PATH: nextCursor
  OCEAN__INITIALIZE_PORT_RESOURCES: "true"
  OCEAN__SEND_RAW_DATA_EXAMPLES: "true"
  OCEAN__EVENT_LISTENER: '{"type":"ONCE"}'
  OCEAN__PORT__BASE_URL: https://api.getport.io
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: n8n-integration
spec:
  replicas: 1
  selector:
    matchLabels:
      app: n8n-integration
  template:
    metadata:
      labels:
        app: n8n-integration
    spec:
      containers:
      - name: custom
        image: ghcr.io/port-labs/port-ocean-custom:latest
        envFrom:
        - configMapRef:
            name: n8n-integration-config
        - secretRef:
            name: n8n-integration-secrets
```

Apply with:

```bash
kubectl apply -f n8n-integration.yaml
```

## Docker Compose

```yaml
version: '3.8'

services:
  n8n-integration:
    image: ghcr.io/port-labs/port-ocean-custom:latest
    container_name: n8n-integration
    restart: unless-stopped
    environment:
      # Port Configuration
      OCEAN__PORT__CLIENT_ID: ${PORT_CLIENT_ID}
      OCEAN__PORT__CLIENT_SECRET: ${PORT_CLIENT_SECRET}
      OCEAN__PORT__BASE_URL: https://api.getport.io
      # Integration Configuration
      OCEAN__INTEGRATION__IDENTIFIER: n8n-integration
      OCEAN__INTEGRATION__CONFIG__BASE_URL: https://your-instance.com/api
      OCEAN__INTEGRATION__CONFIG__AUTH_TYPE: api_key
      OCEAN__INTEGRATION__CONFIG__API_KEY_HEADER: X-N8N-API-KEY
      OCEAN__INTEGRATION__CONFIG__API_KEY: ${N8N_API_KEY}
      OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE: cursor
      OCEAN__INTEGRATION__CONFIG__PAGINATION_PARAM: cursor
      OCEAN__INTEGRATION__CONFIG__SIZE_PARAM: limit
      OCEAN__INTEGRATION__CONFIG__PAGE_SIZE: 100
      OCEAN__INTEGRATION__CONFIG__CURSOR_PATH: nextCursor
      OCEAN__INTEGRATION__CONFIG__HAS_MORE_PATH: nextCursor
      OCEAN__INITIALIZE_PORT_RESOURCES: "true"
      OCEAN__SEND_RAW_DATA_EXAMPLES: "true"
      OCEAN__EVENT_LISTENER: '{"type":"ONCE"}'
```

Create a `.env` file:

```env
PORT_CLIENT_ID=<ENTER PORT CLIENT ID>
PORT_CLIENT_SECRET=<ENTER PORT CLIENT SECRET>
N8N_API_KEY=<ENTER N8N API KEY>
```

Run with:

```bash
docker-compose up -d
```

## Key Configuration Notes

### Authentication
n8n uses API Key authentication:
- **Header**: `X-N8N-API-KEY`
- **API Key**: Your n8n API key

### Pagination
n8n uses cursor-based pagination:
- **Type**: `cursor`
- **Pagination Param**: `cursor` (query parameter)
- **Size Param**: `limit` (query parameter)
- **Cursor Path**: `nextCursor` (JSON path to extract next cursor)
- **Has More Path**: `nextCursor` (JSON path to check if more pages exist)

### Data Extraction
The integration uses `data_path` to extract arrays from n8n's responses:
- Users: `data_path: .data`
- Projects: `data_path: .data`
- Workflows: `data_path: .data`

### API Reference
- [n8n Projects API](https://docs.n8n.io/api/api-reference/#tag/projects/get/projects)
- [n8n Users API](https://docs.n8n.io/api/api-reference/#tag/user/get/users)
- [n8n Workflows API](https://docs.n8n.io/api/api-reference/#tag/workflow/get/workflows)
