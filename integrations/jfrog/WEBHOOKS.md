# JFrog Webhook Configuration

This integration supports real-time updates via JFrog webhooks. When enabled, changes in JFrog will be immediately reflected in Port without waiting for the next scheduled sync.

## Supported Events

### Artifact Events
- **Artifact Deployed** - When an artifact is deployed to a repository
- **Artifact Deleted** - When an artifact is deleted from a repository
- **Artifact Moved** - When an artifact is moved between repositories
- **Artifact Copied** - When an artifact is copied to another repository

### Build Events
- **Build Uploaded** - When a build is uploaded to JFrog
- **Build Deleted** - When a build is deleted
- **Build Promoted** - When a build is promoted

### Docker Events
- **Docker Tag Pushed** - When a Docker tag is pushed to a repository
- **Docker Tag Deleted** - When a Docker tag is deleted

## Setting Up Webhooks in JFrog

### Prerequisites
- Admin access to your JFrog instance
- The Ocean integration must be deployed and running
- Webhook URL from Port (obtained after deploying the integration)

### Configuration Steps

1. **Log in to JFrog** as a user with admin privileges

2. **Navigate to Webhooks**
   - Click the gear icon at the top right corner
   - Choose **Platform Management**
   - At the bottom of the sidebar, choose **Webhooks**

3. **Create Artifact Webhook**
   - Click **Create a WebHook**
   - **Name**: `Port-Artifact`
   - **Description**: `Send artifact events to Port`
   - **URL**: Enter the webhook URL provided by Port
   - **Events**: Under **Artifacts**, select:
     - ✅ Artifact was deployed
     - ✅ Artifact was deleted (optional)
     - ✅ Artifact was moved (optional)
     - ✅ Artifact was copied (optional)
   - **Repositories**: Select all repositories that apply
   - Click **Create**

4. **Create Build Webhook**
   - Click **Create a WebHook**
   - **Name**: `Port-Build`
   - **Description**: `Send build events to Port`
   - **URL**: Enter the webhook URL provided by Port
   - **Events**: Under **Builds**, select:
     - ✅ Build was uploaded
     - ✅ Build was deleted (optional)
     - ✅ Build was promoted (optional)
   - **Builds**: Select all builds that apply
   - Click **Create**

5. **Create Docker Webhook**
   - Click **Create a WebHook**
   - **Name**: `Port-Docker-Tag`
   - **Description**: `Send Docker events to Port`
   - **URL**: Enter the webhook URL provided by Port
   - **Events**: Under **Docker**, select:
     - ✅ Docker tag was pushed
     - ✅ Docker tag was deleted (optional)
   - **Repositories**: Select all Docker repositories that apply
   - Click **Create**

## Webhook URL Configuration

When setting up webhooks in JFrog, use the following URL format:

```
https://your-port-ocean-url/webhook
```

**Note**: All JFrog webhook events (artifacts, builds, Docker tags) should point to the same `/webhook` endpoint. The integration will automatically route events to the appropriate processor based on the event type.

## Webhook Payload Examples

### Artifact Deployed Event
```json
{
  "event_type": "deployed",
  "data": {
    "path": "libs-release-local/com/example/app/1.0.0/app-1.0.0.jar",
    "name": "app-1.0.0.jar",
    "repo_key": "libs-release-local",
    "size": 1024000,
    "created": "2024-01-15T10:30:00.000Z",
    "modified": "2024-01-15T10:30:00.000Z",
    "sha256": "abc123..."
  }
}
```

### Build Uploaded Event
```json
{
  "build_name": "sample_build_name",
  "event_type": "uploaded",
  "build_number": "1",
  "build_started": "2024-01-15T14:40:49.869+0300"
}
```

### Docker Tag Pushed Event
```json
{
  "event_type": "pushed",
  "data": {
    "repo_key": "docker-local",
    "image_name": "myapp",
    "tag": "v1.0.0",
    "digest": "sha256:abc123..."
  }
}
```

## Testing Webhooks

After setting up webhooks, you can test them by:

1. **Deploy an artifact** to a monitored repository
2. **Upload a build** to JFrog
3. **Push a Docker image** to a monitored Docker repository

Check the Port catalog to verify that entities are created/updated in real-time.

## Troubleshooting

### Webhook Not Triggering

1. **Verify webhook URL** - Ensure the URL is correct and accessible
2. **Check JFrog logs** - Look for webhook delivery errors in JFrog logs
3. **Verify events** - Ensure the correct events are selected in webhook configuration
4. **Check repository selection** - Verify that the repositories are included in the webhook

### Events Not Appearing in Port

1. **Check integration logs** - Look for errors in the Ocean integration logs
2. **Verify blueprint mapping** - Ensure blueprints exist in Port
3. **Check webhook payload** - Verify the payload structure matches expected format

## Security Considerations

- **Use HTTPS** - Always use HTTPS for webhook URLs
- **Webhook secrets** - Consider implementing webhook signature verification
- **Network access** - Ensure JFrog can reach the webhook endpoint
- **Authentication** - The integration uses the configured access token for API calls

## Additional Resources

- [JFrog Webhook Documentation](https://jfrog.com/help/r/jfrog-platform-administration-documentation/webhooks)
- [JFrog Event Types](https://jfrog.com/help/r/jfrog-platform-administration-documentation/event-types)
- [Port Webhook Documentation](https://docs.port.io/build-your-software-catalog/custom-integration/webhook/)
