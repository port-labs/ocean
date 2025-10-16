# Harbor Webhook Integration

This module handles real-time Harbor webhook events to keep Port entities synchronized with Harbor changes.

## Supported Events

### Artifact Events
- **PUSH_ARTIFACT**: When an artifact is pushed to Harbor
- **PULL_ARTIFACT**: When an artifact is pulled from Harbor
- **DELETE_ARTIFACT**: When an artifact is deleted from Harbor
- **SCANNING_COMPLETED**: When artifact vulnerability scanning completes

### Repository Events
- **PUSH_ARTIFACT**: Repository metadata updated when artifacts are pushed
- **PULL_ARTIFACT**: Repository pull count updated when artifacts are pulled
- **DELETE_ARTIFACT**: Repository metadata updated when artifacts are deleted

## Configuration

### Harbor Webhook Setup

1. **Configure Harbor Webhook**:
   - Go to your Harbor project settings
   - Navigate to "Webhooks" section
   - Create a new webhook policy with:
     - **Endpoint URL**: `https://your-port-ocean-instance.com/webhook`
     - **Event Types**: Select the events you want to monitor
     - **Notification Type**: HTTP
     - **Payload Format**: JSON (default)

2. **Configure Integration Secret**:
   - Set the `webhook_secret` in your Harbor integration configuration
   - This secret will be used to validate webhook signatures

### Integration Configuration

Add webhook configuration to your Harbor integration:

```yaml
# In your integration configuration
webhook_secret: "your-harbor-webhook-secret"
```

## Webhook Payload Format

Harbor sends webhook payloads in this format:

```json
{
  "type": "PUSH_ARTIFACT",
  "occur_at": 1672531200,
  "operator": "dev-user",
  "event_data": {
    "resources": [
      {
        "digest": "sha256:abcdef123456...",
        "tag": "v1.2.0",
        "resource_url": "https://harbor.example.com/project/repo:v1.2.0"
      }
    ],
    "repository": {
      "name": "repo",
      "namespace": "project",
      "repo_full_name": "project/repo",
      "project_id": 2,
      "repository_id": 1
    }
  }
}
```

## Security

The webhook processors validate incoming requests using HMAC-SHA256 signature verification:

1. Harbor sends the webhook secret in the `Authorization` header as `Harbor-Secret <token>`
2. The processor computes the HMAC-SHA256 of the payload using the configured secret
3. The computed signature is compared with the received signature for validation

## Error Handling

- Invalid or missing signatures are logged and rejected
- Missing required data in webhook payloads is logged and skipped
- Failed API calls to fetch updated data are logged but don't fail the webhook processing
- All webhook processing errors are logged for debugging

## Testing

To test webhook functionality:

1. Configure a Harbor webhook pointing to your integration
2. Perform actions in Harbor (push/pull/delete artifacts)
3. Check the integration logs for webhook processing messages
4. Verify that Port entities are updated accordingly
