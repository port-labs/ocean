## HubSpot – Helm installation example

Replace the placeholders with your values and run:

```bash
helm upgrade --install port-ocean-hubspot port-labs/port-ocean \
  --namespace port-ocean --create-namespace \
  --set integration.identifier="hubspot-integration" \
  --set integration.type="custom" \
  --set integration.version="0.1.0-dev" \
  --set integration.config.base_url="https://api.hubapi.com" \
  --set integration.config.auth_type="bearer_token" \
  --set integration.secrets.apiToken="$HUBSPOT_API_TOKEN" \
  --set integration.config.pagination_type="cursor" \
  --set integration.config.page_size="100" \
  --set integration.config.pagination_param="after" \
  --set integration.config.size_param="limit" \
  --set integration.config.cursor_path="paging.next.after" \
  --set integration.config.has_more_path="paging.next" \
  --set port.clientId="$PORT_CLIENT_ID" \
  --set port.clientSecret="$PORT_CLIENT_SECRET" \
  --set port.baseUrl="https://api.getport.io" \
  --set initializePortResources=true \
  --set sendRawDataExamples=true \
  --set scheduledResyncInterval=1440
```

Environment variables to export before running:

```bash
export PORT_CLIENT_ID=your_port_client_id
export PORT_CLIENT_SECRET=your_port_client_secret
export HUBSPOT_API_TOKEN=your_hubspot_private_app_token
```

Alternatively, use the provided values file:

```bash
export PORT_CLIENT_ID=... PORT_CLIENT_SECRET=... HUBSPOT_API_TOKEN=...
envsubst < integrations/custom/examples/hubspot/helm-values.yaml > /tmp/hubspot-values.yaml
helm upgrade --install port-ocean-hubspot port-labs/port-ocean -n port-ocean --create-namespace -f /tmp/hubspot-values.yaml
```

# HubSpot Integration Installation Guide

This guide will help you set up the HubSpot integration using Port Ocean's Ocean Custom integration with proper cursor-based pagination.

## Prerequisites

1. **Port Account**: Active Port account with API credentials
2. **HubSpot Account**: Active HubSpot account with admin access
3. **Kubernetes Cluster**: Running Kubernetes cluster with kubectl access
4. **Helm**: Helm 3.x installed

## Step 1: Get Your HubSpot Access Token

### Create a Private App in HubSpot

1. Log in to your HubSpot account
2. Navigate to **Settings** (gear icon) → **Integrations** → **Private Apps**
3. Click **Create a private app**
4. Give it a name like "Port Ocean Integration"
5. Go to the **Scopes** tab and enable:
   - `crm.objects.contacts.read`
   - `crm.objects.companies.read`
   - `crm.objects.deals.read`
   - `crm.schemas.custom.read` (for custom objects like feature_requests)
6. Click **Create app**
7. Copy your **Access Token** (starts with `pat-na1-...`)

⚠️ **Keep your access token secure!** Treat it like a password.

## Step 2: Install Port Blueprints

First, create the blueprints in your Port account:

```bash
# Upload the blueprints to Port
curl -X POST 'https://api.getport.io/v1/blueprints' \
  -H 'Authorization: Bearer YOUR_PORT_ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d @blueprints.json
```

Or manually import the `blueprints.json` file through the Port UI:
- Go to your Port account → **Builder** → **Data Model**
- Click **Import** and upload the `blueprints.json` file

## Step 3: Understanding HubSpot's Pagination

HubSpot uses **cursor-based pagination** (not limit/offset). Here's how it works:

### Request
```
GET /crm/v3/objects/contacts?limit=100
```

### Response
```json
{
  "results": [...],
  "paging": {
    "next": {
      "after": "304",
      "link": "https://api.hubapi.com/crm/objects/v3/contacts?limit=100&after=304"
    }
  }
}
```

### Next Request
```
GET /crm/v3/objects/contacts?limit=100&after=304
```

The Ocean integration needs to be configured to:
1. Extract the `after` cursor from `.paging.next.after`
2. Pass it as the `after` query parameter in the next request
3. Stop when `paging.next` is not present

## Step 4: Install Using Helm with Pagination Config

### Option A: Basic Installation with Inline Config

```bash
helm install port-ocean-hubspot port-labs/port-ocean \
  --set port.clientId=YOUR_PORT_CLIENT_ID \
  --set port.clientSecret=YOUR_PORT_CLIENT_SECRET \
  --set integration.identifier=hubspot-integration \
  --set integration.type=custom \
  --set integration.version=0.1.0-dev \
  --set integration.config.baseUrl=https://api.hubapi.com \
  --set integration.config.authType=bearer \
  --set integration.secrets.token=YOUR_HUBSPOT_ACCESS_TOKEN \
  --set 'integration.config.pagination.pagination_type=cursor' \
  --set 'integration.config.pagination.cursor_path=.paging.next.after' \
  --set 'integration.config.pagination.cursor_query_param=after' \
  --set 'integration.config.pagination.limit_query_param=limit' \
  --set 'integration.config.pagination.limit=100' \
  --set initializePortResources=true \
  --set sendRawDataExamples=true
```

Replace:
- `YOUR_PORT_CLIENT_ID` - Your Port client ID
- `YOUR_PORT_CLIENT_SECRET` - Your Port client secret
- `YOUR_HUBSPOT_ACCESS_TOKEN` - Your HubSpot access token (e.g., `pat-na1-xxxxx`)

### Option B: With Custom Configuration File (Recommended)

First, create a ConfigMap with the port-app-config.yml:

```bash
kubectl create configmap hubspot-integration-config \
  --from-file=port-app-config.yml
```

Then install with the ConfigMap:

```bash
helm install port-ocean-hubspot port-labs/port-ocean \
  --set port.clientId=YOUR_PORT_CLIENT_ID \
  --set port.clientSecret=YOUR_PORT_CLIENT_SECRET \
  --set integration.identifier=hubspot-integration \
  --set integration.type=custom \
  --set integration.version=0.1.0-dev \
  --set integration.config.baseUrl=https://api.hubapi.com \
  --set integration.config.authType=bearer \
  --set integration.secrets.token=YOUR_HUBSPOT_ACCESS_TOKEN \
  --set-file integration.config.mappings=port-app-config.yml \
  --set initializePortResources=true
```

## Step 5: Verify Pagination is Working

Check the integration logs to ensure pagination is functioning:

```bash
# View logs
kubectl logs -l app.kubernetes.io/instance=port-ocean-hubspot --tail=100

# Follow logs in real-time
kubectl logs -l app.kubernetes.io/instance=port-ocean-hubspot --follow
```

You should see log entries like:
```
INFO: Fetching data from GET https://api.hubapi.com/crm/v3/objects/contacts with pagination: cursor
INFO: Found 100 items, cursor: 304
INFO: Fetching next page with cursor: 304
INFO: Found 100 items, cursor: 608
...
INFO: No more pages, pagination complete
```

## Step 6: Verify Data in Port

1. Log in to your Port account
2. Navigate to the **Catalog**
3. You should see new entities:
   - **Ocean HubSpot Contacts** - All your CRM contacts
   - **Ocean HubSpot Companies** - Your organizations
   - **Ocean HubSpot Deals** - Sales opportunities
   - **Ocean HubSpot Feature Requests** - Product roadmap items

## HubSpot API Details

### Authentication
HubSpot uses Bearer Token authentication:

```
Authorization: Bearer pat-na1-xxxxx
```

### Pagination Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `limit` | Number of results per page (max 100) | `?limit=100` |
| `after` | Cursor for next page | `?after=304` |

### Response Structure

All HubSpot CRM objects follow this pattern:

```json
{
  "results": [
    {
      "id": "123",
      "properties": { ... },
      "createdAt": "2024-01-01T00:00:00Z",
      "updatedAt": "2024-01-02T00:00:00Z"
    }
  ],
  "paging": {
    "next": {
      "after": "456"
    }
  }
}
```

### Available Endpoints

| Endpoint | Description | Method | Pagination |
|----------|-------------|--------|------------|
| `/crm/v3/objects/contacts` | List all contacts | GET | Cursor-based |
| `/crm/v3/objects/companies` | List companies | GET | Cursor-based |
| `/crm/v3/objects/deals` | List deals | GET | Cursor-based |
| `/crm/v3/objects/2-24903472` | List feature requests (custom) | GET | Cursor-based |
| `/crm/v3/pipelines/deals` | List deal pipelines | GET | No pagination |
| `/crm/v3/schemas` | List custom object schemas | GET | No pagination |

### Custom Objects

To find your custom object IDs:

```bash
curl -X GET "https://api.hubapi.com/crm/v3/schemas" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Look for the `objectTypeId` field (e.g., `2-24903472` for feature_requests).

## Step 7: Configure Resources with Pagination

Each resource in `port-app-config.yml` specifies how to handle pagination:

```yaml
resources:
  - kind: /crm/v3/objects/contacts
    selector:
      query: "true"
      method: GET
      data_path: .results  # Extract items from results array
      # Pagination is configured globally, not per-resource
    port:
      entity:
        mappings:
          identifier: .id
          title: .properties.email
          blueprint: '"ocean_hubspotContact"'
          # ...
```

The global pagination config (from Helm install) applies to all resources:
- `pagination_type: cursor` - Use cursor-based pagination
- `cursor_path: .paging.next.after` - Where to find next cursor
- `cursor_query_param: after` - Query param name for cursor
- `limit_query_param: limit` - Query param name for page size
- `limit: 100` - Max items per page (HubSpot max is 100)

## Troubleshooting

### Pod is not starting

```bash
kubectl describe pod -l app.kubernetes.io/instance=port-ocean-hubspot
```

Common issues:
- **ImagePullBackOff**: Image version might not be available
- **Authentication errors**: Check your HubSpot access token
- **Port credentials**: Verify your Port client ID and secret

### No data appearing in Port

1. Check the integration logs:
```bash
kubectl logs -l app.kubernetes.io/instance=port-ocean-hubspot --tail=100
```

2. Verify your HubSpot access token is valid:
```bash
curl -X GET "https://api.hubapi.com/crm/v3/objects/contacts?limit=1" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

3. Ensure blueprints are created in Port
4. Check that the `port-app-config.yml` mapping is correct

### Pagination Not Working

Check logs for errors like:
- `Cursor path not found` - Verify `cursor_path` is correct
- `Rate limit exceeded` - Add delay between requests
- `Invalid cursor` - The cursor might have expired

To debug pagination:
```bash
# Enable debug logging
kubectl set env deployment/port-ocean-hubspot LOG_LEVEL=DEBUG
```

### Rate Limiting

HubSpot has API rate limits:
- **Free/Starter**: 100 requests per 10 seconds
- **Professional/Enterprise**: Higher limits

If you hit rate limits:
- Reduce the `limit` per page (though this increases total requests)
- Add delays in Ocean configuration
- Contact HubSpot support for higher limits

## Custom Object Configuration

For the `feature_requests` custom object, you need to:

1. Find the objectTypeId (it's `2-24903472` in this example)
2. Specify properties to fetch in the query parameters:

```yaml
resources:
  - kind: /crm/v3/objects/2-24903472
    selector:
      query: "true"
      method: GET
      query_params:
        properties: "name,title,status,votes,promised,planned,product_eta,team,url"
      data_path: .results
```

## Performance Optimization

### Concurrent Requests
The Ocean integration supports concurrent API calls:

```bash
--set integration.config.max_concurrent_requests=5
```

### Batch Size
Adjust the page size for optimal performance:

```bash
--set integration.config.pagination.limit=100  # HubSpot max is 100
```

### Selective Syncing
Only sync the properties you need:

```yaml
query_params:
  properties: "firstname,lastname,email,createdate"  # Only essential fields
```

## Uninstall

To remove the integration:

```bash
helm uninstall port-ocean-hubspot
```

## Additional Resources

- [HubSpot API Documentation](https://developers.hubspot.com/docs/api/overview)
- [HubSpot CRM API Reference](https://developers.hubspot.com/docs/api/crm/understanding-the-crm)
- [HubSpot Pagination Guide](https://developers.hubspot.com/docs/api/crm/search#pagination)
- [Port Ocean Documentation](https://docs.getport.io/build-your-software-catalog/custom-integration/ocean)
- [Ocean Custom Integration](https://docs.getport.io/build-your-software-catalog/custom-integration/custom)

## Support

For issues or questions:
- Port Support: support@getport.io
- HubSpot Developer Community: community.hubspot.com
- HubSpot API Support: developers.hubspot.com/community

---

**Pro Tip**: Start with a small `limit` value (e.g., 10) when testing to verify pagination works correctly, then increase to 100 for production use.

