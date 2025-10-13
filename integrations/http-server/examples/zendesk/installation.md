# Zendesk Integration Installation Examples

This example demonstrates how to set up the HTTP Server integration with Zendesk using cursor pagination and path parameters.

## Prerequisites

1. Port credentials (`CLIENT_ID` and `CLIENT_SECRET`)
2. Zendesk subdomain (e.g., `yourcompany.zendesk.com`)
3. Zendesk API token (generate from Admin > API > Token)
4. Zendesk email/token format: `your-email@domain.com/token`

## Docker

```bash
docker run -d \
  --name zendesk-integration \
  -e OCEAN__PORT__CLIENT_ID=your_port_client_id \
  -e OCEAN__PORT__CLIENT_SECRET=your_port_client_secret \
  -e OCEAN__INTEGRATION__IDENTIFIER=zendesk-integration \
  -e OCEAN__INTEGRATION__TYPE=http-server \
  -e OCEAN__INTEGRATION__CONFIG__BASE_URL=https://yourcompany.zendesk.com \
  -e OCEAN__INTEGRATION__CONFIG__AUTH_TYPE=basic \
  -e OCEAN__INTEGRATION__CONFIG__USERNAME=your-email@domain.com/token \
  -e OCEAN__INTEGRATION__CONFIG__PASSWORD=your_zendesk_api_token \
  -e OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE=cursor \
  -e OCEAN__INTEGRATION__CONFIG__PAGE_SIZE=100 \
  -e OCEAN__INTEGRATION__CONFIG__PAGINATION_PARAM=page[after] \
  -e OCEAN__INTEGRATION__CONFIG__SIZE_PARAM=page[size] \
  -e OCEAN__INTEGRATION__CONFIG__CURSOR_PATH=meta.after_cursor \
  -e OCEAN__INTEGRATION__CONFIG__HAS_MORE_PATH=meta.has_more \
  -e OCEAN__INITIALIZE_PORT_RESOURCES=true \
  -e OCEAN__SEND_RAW_DATA_EXAMPLES=true \
  port-labs/port-ocean-http-server:latest
```

## Helm

```bash
helm repo add port-labs https://port-labs.github.io/helm-charts
helm repo update

helm install zendesk-integration port-labs/port-ocean-http-server \
  --set port.clientId=your_port_client_id \
  --set port.clientSecret=your_port_client_secret \
  --set integration.identifier=zendesk-integration \
  --set integration.type=http-server \
  --set integration.config.baseUrl=https://yourcompany.zendesk.com \
  --set integration.config.authType=basic \
  --set integration.config.username=your-email@domain.com/token \
  --set integration.secrets.password=your_zendesk_api_token \
  --set integration.config.paginationType=cursor \
  --set integration.config.pageSize=100 \
  --set integration.config.paginationParam=page[after] \
  --set integration.config.sizeParam=page[size] \
  --set integration.config.cursorPath=meta.after_cursor \
  --set integration.config.hasMorePath=meta.has_more \
  --set initializePortResources=true \
  --set sendRawDataExamples=true
```

### Using values.yaml

Create a `zendesk-values.yaml` file:

```yaml
port:
  clientId: your_port_client_id
  clientSecret: your_port_client_secret

integration:
  identifier: zendesk-integration
  type: http-server
  config:
    baseUrl: https://yourcompany.zendesk.com
    authType: basic
    username: your-email@domain.com/token
    paginationType: cursor
    pageSize: 100
    paginationParam: page[after]
    sizeParam: page[size]
    cursorPath: meta.after_cursor
    hasMorePath: meta.has_more
  secrets:
    password: your_zendesk_api_token

initializePortResources: true
sendRawDataExamples: true
```

Then install:

```bash
helm install zendesk-integration port-labs/port-ocean-http-server -f zendesk-values.yaml
```

## Kubernetes

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: zendesk-integration-secrets
type: Opaque
stringData:
  OCEAN__PORT__CLIENT_ID: your_port_client_id
  OCEAN__PORT__CLIENT_SECRET: your_port_client_secret
  OCEAN__INTEGRATION__CONFIG__PASSWORD: your_zendesk_api_token
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: zendesk-integration-config
data:
  OCEAN__INTEGRATION__IDENTIFIER: zendesk-integration
  OCEAN__INTEGRATION__TYPE: http-server
  OCEAN__INTEGRATION__CONFIG__BASE_URL: https://yourcompany.zendesk.com
  OCEAN__INTEGRATION__CONFIG__AUTH_TYPE: basic
  OCEAN__INTEGRATION__CONFIG__USERNAME: your-email@domain.com/token
  OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE: cursor
  OCEAN__INTEGRATION__CONFIG__PAGE_SIZE: "100"
  OCEAN__INTEGRATION__CONFIG__PAGINATION_PARAM: page[after]
  OCEAN__INTEGRATION__CONFIG__SIZE_PARAM: page[size]
  OCEAN__INTEGRATION__CONFIG__CURSOR_PATH: meta.after_cursor
  OCEAN__INTEGRATION__CONFIG__HAS_MORE_PATH: meta.has_more
  OCEAN__INITIALIZE_PORT_RESOURCES: "true"
  OCEAN__SEND_RAW_DATA_EXAMPLES: "true"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zendesk-integration
spec:
  replicas: 1
  selector:
    matchLabels:
      app: zendesk-integration
  template:
    metadata:
      labels:
        app: zendesk-integration
    spec:
      containers:
      - name: http-server
        image: port-labs/port-ocean-http-server:latest
        envFrom:
        - configMapRef:
            name: zendesk-integration-config
        - secretRef:
            name: zendesk-integration-secrets
```

Apply with:

```bash
kubectl apply -f zendesk-integration.yaml
```

## Docker Compose

```yaml
version: '3.8'

services:
  zendesk-integration:
    image: port-labs/port-ocean-http-server:latest
    container_name: zendesk-integration
    restart: unless-stopped
    environment:
      # Port Configuration
      OCEAN__PORT__CLIENT_ID: ${PORT_CLIENT_ID}
      OCEAN__PORT__CLIENT_SECRET: ${PORT_CLIENT_SECRET}
      
      # Integration Configuration
      OCEAN__INTEGRATION__IDENTIFIER: zendesk-integration
      OCEAN__INTEGRATION__TYPE: http-server
      OCEAN__INTEGRATION__CONFIG__BASE_URL: https://yourcompany.zendesk.com
      OCEAN__INTEGRATION__CONFIG__AUTH_TYPE: basic
      OCEAN__INTEGRATION__CONFIG__USERNAME: your-email@domain.com/token
      OCEAN__INTEGRATION__CONFIG__PASSWORD: ${ZENDESK_API_TOKEN}
      
      # Pagination Configuration (Zendesk uses cursor-based pagination)
      OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE: cursor
      OCEAN__INTEGRATION__CONFIG__PAGE_SIZE: 100
      OCEAN__INTEGRATION__CONFIG__PAGINATION_PARAM: page[after]
      OCEAN__INTEGRATION__CONFIG__SIZE_PARAM: page[size]
      OCEAN__INTEGRATION__CONFIG__CURSOR_PATH: meta.after_cursor
      OCEAN__INTEGRATION__CONFIG__HAS_MORE_PATH: meta.has_more
      
      # Optional Settings
      OCEAN__INITIALIZE_PORT_RESOURCES: "true"
      OCEAN__SEND_RAW_DATA_EXAMPLES: "true"
      OCEAN__LOG_LEVEL: INFO
```

Create a `.env` file:

```env
PORT_CLIENT_ID=your_port_client_id
PORT_CLIENT_SECRET=your_port_client_secret
ZENDESK_API_TOKEN=your_zendesk_api_token
```

Run with:

```bash
docker-compose up -d
```

## Key Configuration Notes

### Authentication
Zendesk uses Basic Authentication with a special username format:
- **Username**: `your-email@domain.com/token` (note the `/token` suffix)
- **Password**: Your Zendesk API token

### Pagination
Zendesk uses cursor-based pagination to handle large datasets without limits:
- **Type**: `cursor`
- **Pagination Param**: `page[after]` - Query parameter for cursor
- **Size Param**: `page[size]` - Query parameter for page size
- **Cursor Path**: `meta.after_cursor` - JSON path to extract next cursor
- **Has More Path**: `meta.has_more` - JSON path to check if more pages exist

### Path Parameters
The Zendesk example demonstrates path parameter resolution for nested resources:
- Comments are fetched via `/api/v2/tickets/{ticket_id}/comments.json`
- The integration automatically resolves `{ticket_id}` by querying `/api/v2/tickets.json` first
- The resolved `ticket_id` is injected as `.__ticket_id` in the entity data for use in mappings

### Data Extraction
The integration uses `data_path` to extract arrays from Zendesk's nested responses:
- Tickets: `data_path: .tickets`
- Users: `data_path: .users`
- Organizations: `data_path: .organizations`
- Comments: `data_path: .comments`

