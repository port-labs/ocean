# Slack Integration for Port

This integration syncs Slack workspace data to Port, including channels, users, and channel memberships. It provides real-time updates through Slack's Events API and handles rate limiting for reliable data synchronization.

## Prerequisites

1. A Slack workspace where you are an administrator
2. A Slack app with the following OAuth scopes:
   - `channels:read` - For reading channel information
   - `channels:history` - For accessing channel membership data
   - `users:read` - For reading user information
   - `users:read.email` - For accessing user email addresses (optional)

## Setup Instructions

### 1. Create a Slack App

1. Go to [Slack API Apps page](https://api.slack.com/apps)
2. Click "Create New App"
3. Choose "From scratch"
4. Name your app and select your workspace
5. Click "Create App"

### 2. Configure OAuth Scopes

1. In your app settings, navigate to "OAuth & Permissions"
2. Under "Scopes", add the following Bot Token Scopes:
   - `channels:read`
   - `channels:history`
   - `users:read`
   - `users:read.email` (optional)
3. Install the app to your workspace
4. Copy the "Bot User OAuth Token" - you'll need this for configuration

### 3. Configure Event Subscriptions

1. In your app settings, go to "Event Subscriptions"
2. Enable events
3. Set the Request URL to your Ocean integration's webhook endpoint
4. Subscribe to the following bot events:
   - `channel_created`
   - `channel_deleted`
   - `channel_rename`
   - `channel_archive`
   - `channel_unarchive`
   - `member_joined_channel`
   - `member_left_channel`
   - `team_join`
   - `user_change`

### 4. Configure the Integration

Add the following to your Ocean integration configuration:

```yaml
resources:
  - kind: channel
    selector: {}
  - kind: user
    selector: {}
  - kind: channel_member
    selector: {}

integration:
  identifier: "slack"
  type: "slack"
  config:
    token: "xoxb-your-token-here"  # Bot User OAuth Token
```

## Rate Limiting

The integration implements automatic rate limiting handling according to Slack's API guidelines:

- Respects Slack's rate limits (Tier 3: 50+ requests per minute)
- Implements exponential backoff for rate limit errors
- Automatically retries failed requests
- Logs rate limit warnings and errors

Rate limit handling is implemented in the following ways:

1. **Automatic Retry**: When a rate limit is hit, the integration will:
   - Parse the `Retry-After` header
   - Wait for the specified duration
   - Automatically retry the request

2. **Concurrent Request Management**:
   - Implements request queuing
   - Maintains separate rate limits for different API methods
   - Logs detailed rate limit information for monitoring

## Data Flow

The integration maintains data synchronization through two main paths:

1. **Initial/Resync Data Load**:
   ```
   Slack API → Ocean Integration → Port
   ```
   - Fetches all channels and users
   - Processes channel memberships
   - Applies data transformations
   - Syncs to Port

2. **Real-time Updates** (via Events API):
   ```
   Slack Events → Webhook → Ocean Integration → Port
   ```
   - Receives Slack events in real-time
   - Processes event data
   - Updates affected resources
   - Syncs changes to Port

### Data Processing

The integration processes data securely and handles PII (Personally Identifiable Information) appropriately:

- Masks sensitive user information (email, real name)
- Processes data on-premises
- Implements secure token handling
- Validates and sanitizes all data before sync

## Troubleshooting

Common issues and solutions:

1. **Rate Limiting**:
   - Check logs for rate limit warnings
   - Adjust sync intervals if needed
   - Monitor rate limit metrics

2. **Event Subscription**:
   - Verify webhook URL is accessible
   - Check event subscription status
   - Validate bot token scopes

3. **Data Sync Issues**:
   - Verify token permissions
   - Check resource configurations
   - Review transformation rules

## Support

For issues and feature requests, please:
1. Check the troubleshooting guide above
2. Review Port's documentation
3. Contact Port support if issues persist
