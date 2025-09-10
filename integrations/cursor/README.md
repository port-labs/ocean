# Cursor Integration

This is a Port Ocean integration for [Cursor AI IDE](https://cursor.sh/), allowing you to sync utilization data, AI metrics, and team information from Cursor into your Port workspace.

## Features

- **Team Management**: Sync team information and member details
- **Daily Usage Metrics**: Track daily usage statistics across your team
- **AI Commit Tracking**: Monitor AI-assisted commits and their metrics
- **AI Code Changes**: Track code changes generated or assisted by AI
- **Usage Events**: Detailed event tracking for team activities
- **User-Specific Usage**: Individual user usage patterns and statistics

## Configuration

The integration requires the following configuration parameters:

### Required Configuration

- `api_key` (string): Your Cursor Admin API key
- `team_id` (string): The identifier of your Cursor team

### Optional Configuration

- `usage_start_date` (string, ISO format): Start date for daily usage sync (default: 30 days ago)
- `usage_end_date` (string, ISO format): End date for daily usage sync (default: now)
- `ai_commits_start_date` (string, ISO format): Start date for AI commits sync (default: 30 days ago)
- `ai_commits_end_date` (string, ISO format): End date for AI commits sync (default: now)
- `ai_changes_start_date` (string, ISO format): Start date for AI code changes sync (default: 30 days ago)
- `ai_changes_end_date` (string, ISO format): End date for AI code changes sync (default: now)
- `events_start_date` (string, ISO format): Start date for usage events sync (default: 7 days ago)
- `events_end_date` (string, ISO format): End date for usage events sync (default: now)
- `filter_user_email` (string): Filter usage events for a specific user email
- `target_users` (array of strings): List of user emails for user-specific daily usage tracking

## Getting Started

### Prerequisites

1. A Cursor account with admin access
2. A Cursor Admin API key
3. Your team identifier

### Obtaining API Credentials

1. Log in to your Cursor account
2. Navigate to team settings or admin panel
3. Generate an Admin API key
4. Note your team identifier from the team settings

### Installation and Setup

1. Install the integration using the Port Ocean CLI:
   ```bash
   port ocean install cursor
   ```

2. Configure the integration with your API credentials:
   ```yaml
   integration:
     config:
       api_key: "your-cursor-api-key"
       team_id: "your-team-id"
   ```

3. Run the integration:
   ```bash
   port ocean run
   ```

## Data Model

The integration creates the following entities in Port:

### Team
- Represents your Cursor team
- Contains team metadata and configuration

### User  
- Represents team members
- Contains user profile information and role details

### Daily Usage
- Daily aggregated usage statistics
- Metrics include active time, AI interactions, and productivity metrics

### AI Commit
- Individual AI-assisted commits
- Contains commit metadata, AI contribution level, and impact metrics

### AI Code Change
- Code changes generated or assisted by AI
- Includes change type, size, and AI assistance level

### Usage Event
- Individual usage events and activities
- Detailed event logs for audit and analysis purposes

## Rate Limits

The Cursor API has the following rate limits:
- 5 requests per minute per team, per endpoint
- The integration includes automatic retry logic with exponential backoff

## Troubleshooting

### Common Issues

**Authentication Errors**
- Verify your API key is correct and has admin permissions
- Ensure your team ID is accurate

**No Data Returned**
- Check your date ranges - data may not be available for the requested period
- Verify your team has activity during the specified time range

**Rate Limit Errors**
- The integration handles rate limiting automatically
- If issues persist, consider adjusting the sync frequency

### Debug Mode

Enable debug logging by setting the log level:
```bash
export LOG_LEVEL=DEBUG
port ocean run
```

## API Reference

This integration uses the Cursor Admin API. The API provides endpoints for:

- Team management and member information
- Daily usage metrics and analytics
- AI-assisted development tracking
- Code change and commit analysis
- Event logging and audit trails

For detailed API documentation, refer to the [Cursor API Documentation](https://api.cursor.com/docs).

## Contributing

We welcome contributions to this integration. Please see our [Contributing Guide](../../CONTRIBUTING.md) for details on:

- Setting up the development environment
- Running tests
- Submitting pull requests
- Code style and standards

## Support

For support and questions:

1. Check the [Port documentation](https://docs.getport.io)
2. Visit the [Port community](https://github.com/port-labs/port-ocean)
3. Contact Port support through your workspace

## License

This integration is licensed under the same terms as Port Ocean.