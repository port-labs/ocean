# Anthropic Ocean Integration

This Ocean integration syncs data from Anthropic's API into your Port software catalog, providing visibility into API usage, costs, and API key management.

## Features

The integration supports syncing the following Anthropic resources:

- **API Keys**: Information about API keys and their metadata
- **Usage Data**: Token consumption metrics, message counts, and model usage statistics  
- **Cost Data**: Billing information, cost breakdowns, and spending analytics

## Prerequisites

- **Anthropic Admin API Key**: You need an admin-level API key from your Anthropic organization to access usage and cost reporting endpoints
- **Organization Access**: The API key must belong to an organization (not individual account) to access usage/cost APIs

## Configuration

### Required Secrets

Configure the following secrets in your Ocean integration:

| Secret | Description | Required | Example |
|--------|-------------|----------|---------|
| `api_key` | Admin API key from Anthropic Console | ✅ | `sk-ant-api03-xxx...` |
| `base_url` | Anthropic API base URL | ❌ | `https://api.anthropic.com` |

### Getting Your API Key

1. Go to the [Anthropic Console](https://console.anthropic.com/account/keys)
2. Navigate to Account Settings → API Keys
3. Create a new API key with admin permissions
4. Copy the key (starts with `sk-ant-api03-`)

> **Important**: You need an admin-level API key to access usage and cost reporting endpoints. Regular API keys will not work for this integration.

## Resource Configuration

### API Keys

Syncs information about your organization's API keys:

```yaml
resources:
  - kind: api-key
    selector:
      include_metadata: true  # Include additional metadata about API keys
```

### Usage Data

Syncs token consumption and usage metrics:

```yaml  
resources:
  - kind: usage
    selector:
      time_bucket: "1d"           # Aggregation granularity: 1m, 1h, or 1d
      days_back: 30               # Number of days to fetch (1-90)
      include_models:             # Optional: filter by specific models
        - "claude-3-opus-20240229"
        - "claude-3-sonnet-20240229"
      include_workspaces:         # Optional: filter by workspaces
        - "workspace-123"
```

### Cost Data

Syncs billing and cost information:

```yaml
resources:
  - kind: costs  
    selector:
      days_back: 30               # Number of days to fetch (1-90)
      include_workspaces:         # Optional: filter by workspaces  
        - "workspace-123"
      currency: "USD"             # Currency for reporting (USD only)
```

## Data Models

### API Key Entity

```json
{
  "id": "key_1234",
  "key_prefix": "sk-ant-api...",
  "organization_id": "org_xxx",
  "created_at": "2024-01-01T00:00:00Z",
  "status": "active",
  "type": "admin"
}
```

### Usage Entity  

```json
{
  "time_bucket": "2024-01-01T00:00:00Z",
  "model": "claude-3-opus-20240229",
  "input_tokens": 1000,
  "output_tokens": 500,
  "message_count": 10,
  "workspace_id": "workspace-123",
  "service_tier": "scale"
}
```

### Cost Entity

```json
{
  "date": "2024-01-01",
  "total_cost_usd": 12.50,
  "token_cost_usd": 10.00,  
  "search_cost_usd": 1.50,
  "execution_cost_usd": 1.00,
  "workspace_id": "workspace-123",
  "model": "claude-3-opus-20240229"
}
```

## API Documentation References

This integration is based on the following Anthropic API documentation:

- **Main API Docs**: https://docs.anthropic.com/en/api
- **Usage & Cost API**: https://docs.anthropic.com/en/api/usage-cost-api  
- **Rate Limits**: https://docs.anthropic.com/en/api/rate-limits
- **Authentication**: https://docs.anthropic.com/en/api/overview#authentication

## Rate Limiting

The integration handles Anthropic's rate limits automatically with:

- Exponential backoff for rate-limited requests  
- Respect for `retry-after` headers
- Configurable request timeouts
- Automatic retry logic for transient failures

## Local Development

### Testing the Integration

1. Install dependencies:
   ```bash
   make install
   ```

2. Set environment variables:
   ```bash
   export ANTHROPIC_API_KEY="your-admin-api-key"  
   ```

3. Run tests:
   ```bash
   make run-tests
   ```

4. Build and run locally:
   ```bash
   make run-local
   ```

### Testing API Connection

Use the debug script to test your API connection:

```python
from client import create_anthropic_client

client = create_anthropic_client()
connection_ok = await client.test_connection()
print(f"Connection successful: {connection_ok}")
```

## Troubleshooting

### Authentication Errors

- **403 Forbidden**: Your API key lacks admin permissions
- **401 Unauthorized**: Invalid or expired API key
- **404 Not Found**: API key not associated with an organization

### Rate Limiting Issues

- The integration automatically handles rate limits
- For high-volume usage, consider increasing `time_bucket` to reduce API calls
- Limit the `days_back` parameter to reduce data volume

### Missing Data

- Usage/cost data may have a 5-minute delay from Anthropic  
- Ensure your organization has usage during the selected time period
- Check that your API key has access to the specific workspaces

## Support

For issues specific to this integration, please check:

1. Your API key has admin permissions
2. Your organization has usage data in the selected time range  
3. The Anthropic API is accessible from your environment

For Anthropic API issues, refer to their [official documentation](https://docs.anthropic.com) or contact Anthropic support.