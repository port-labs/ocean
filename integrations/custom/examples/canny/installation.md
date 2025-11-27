# Canny Integration Installation Guide

This guide will help you set up the Canny integration using Port Ocean's Ocean Custom integration.

## Prerequisites

1. **Port Account**: Active Port account with API credentials
2. **Canny Account**: Active Canny account with admin access
3. **Kubernetes Cluster**: Running Kubernetes cluster with kubectl access
4. **Helm**: Helm 3.x installed

## Step 1: Get Your Canny API Key

1. Log in to your Canny account
2. Go to **Settings** → **API & Webhooks**
3. Copy your **API Key** (keep it secure!)

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

## Step 3: Prepare Configuration

The integration uses the following Canny API endpoints:

- **Boards**: `https://canny.io/api/v1/boards/list`
- **Categories**: `https://canny.io/api/v1/categories/list`
- **Posts**: `https://canny.io/api/v1/posts/list`
- **Companies**: `https://canny.io/api/v1/companies/list`
- **Votes**: `https://canny.io/api/v1/votes/list`

### Authentication Details

- **Method**: API Key (sent in POST body)
- **Header**: `Content-Type: application/json`

## Step 4: Install Using Helm

### Option A: Basic Installation (Recommended)

**Important**: Canny requires API key authentication via query parameter. We embed it in the base URL:

```bash
helm install port-ocean-canny port-labs/port-ocean \
  --set port.clientId=YOUR_PORT_CLIENT_ID \
  --set port.clientSecret=YOUR_PORT_CLIENT_SECRET \
  --set integration.identifier=canny-integration \
  --set integration.type=custom \
  --set integration.version=0.1.0-dev \
  --set 'integration.config.baseUrl=https://canny.io/api/v1?apiKey=YOUR_CANNY_API_KEY' \
  --set integration.config.authType=none \
  --set initializePortResources=true \
  --set sendRawDataExamples=true
```

Replace:
- `YOUR_PORT_CLIENT_ID` - Your Port client ID
- `YOUR_PORT_CLIENT_SECRET` - Your Port client secret
- `YOUR_CANNY_API_KEY` - Your Canny API key (embedded in baseUrl)

**Note**: The API key is embedded in the base URL as a query parameter because Canny uses a non-standard authentication approach.

### Option B: With Custom Configuration

If you want to customize the data mapping, first create a ConfigMap:

```bash
kubectl create configmap canny-integration-config \
  --from-file=port-app-config.yml
```

Then install with the ConfigMap:

```bash
helm install port-ocean-canny port-labs/port-ocean \
  --set port.clientId=YOUR_PORT_CLIENT_ID \
  --set port.clientSecret=YOUR_PORT_CLIENT_SECRET \
  --set integration.identifier=canny-integration \
  --set integration.type=custom \
  --set integration.version=0.1.0-dev \
  --set integration.config.baseUrl=https://canny.io/api/v1 \
  --set integration.secrets.apiKey=YOUR_CANNY_API_KEY \
  --set-file integration.config.mappings=port-app-config.yml \
  --set initializePortResources=true
```

## Step 5: Configure API Endpoints

The Canny API requires specific endpoint configurations. You'll need to configure these in Port after installation:

### Resource Configuration

Add these resource configurations to your integration in Port:

#### Boards
```yaml
- kind: board
  selector:
    query: "true"
  port:
    entity:
      mappings:
        identifier: .id
        title: .name
        blueprint: '"ocean_cannyBoard"'
```

#### Posts
```yaml
- kind: post
  selector:
    query: "true"
  port:
    entity:
      mappings:
        identifier: .id
        title: .title
        blueprint: '"ocean_cannyPost"'
```

## Step 6: Verify Installation

Check if the integration is running:

```bash
# Check pod status
kubectl get pods -l app.kubernetes.io/instance=port-ocean-canny

# View logs
kubectl logs -l app.kubernetes.io/instance=port-ocean-canny --tail=50

# Follow logs
kubectl logs -l app.kubernetes.io/instance=port-ocean-canny --follow
```

Expected output should show:
- ✅ Ocean version
- ✅ Integration initialized
- ✅ Kafka consumer started
- ✅ Data syncing from Canny

## Step 7: Verify Data in Port

1. Log in to your Port account
2. Navigate to the **Catalog**
3. You should see new entities:
   - **Ocean Canny Boards** - All your Canny boards
   - **Ocean Canny Posts** - Feature requests
   - **Ocean Canny Categories** - Board categories
   - **Ocean Canny Companies** - Customer companies
   - **Ocean Canny Votes** - Individual user votes

## Canny API Details

### Authentication
Canny uses POST requests with the API key in the request body:

```json
{
  "apiKey": "YOUR_API_KEY"
}
```

### Pagination
Canny uses limit/skip pagination:
- `limit`: Number of results per page (max 100)
- `skip`: Number of results to skip

### Available Endpoints

| Endpoint | Description | Method |
|----------|-------------|--------|
| `/boards/list` | List all boards | POST |
| `/categories/list` | List categories | POST |
| `/posts/list` | List feature requests | POST |
| `/companies/list` | List companies | POST |
| `/votes/list` | List individual votes | POST |
| `/comments/list` | List comments (optional) | POST |

## Troubleshooting

### Pod is not starting

```bash
kubectl describe pod -l app.kubernetes.io/instance=port-ocean-canny
```

Common issues:
- **ImagePullBackOff**: Image version might not be available
- **Authentication errors**: Check your Canny API key
- **Port credentials**: Verify your Port client ID and secret

### No data appearing in Port

1. Check the integration logs:
```bash
kubectl logs -l app.kubernetes.io/instance=port-ocean-canny --tail=100
```

2. Verify your Canny API key is valid
3. Ensure blueprints are created in Port
4. Check that the `port-app-config.yml` mapping is correct

### API Rate Limiting

Canny has rate limits. If you encounter rate limiting:
- Reduce sync frequency
- Implement caching strategies
- Contact Canny support for higher limits

## Uninstall

To remove the integration:

```bash
helm uninstall port-ocean-canny
```

## Additional Resources

- [Canny API Documentation](https://developers.canny.io/api-reference)
- [Port Ocean Documentation](https://docs.getport.io/build-your-software-catalog/custom-integration/ocean)
- [Ocean Custom Integration](https://docs.getport.io/build-your-software-catalog/custom-integration/custom)

## Support

For issues or questions:
- Port Support: support@getport.io
- Canny Support: help@canny.io

