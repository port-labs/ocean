# Zendesk Integration

This integration brings information from Zendesk into Port, providing comprehensive visibility into your support operations.

## Features

This integration supports synchronization of the following Zendesk resources:

- **Tickets** - Customer support tickets with full details
- **Side Conversations** - Side conversations within tickets  
- **Users** - End-users, agents, and administrators
- **Organizations** - Customer organizations and companies

The integration supports both full synchronization (resync) and real-time updates via webhooks.

## Prerequisites

- Zendesk account with appropriate permissions
- API token for authentication
- Port Ocean framework

## Configuration

### Required Secrets

The integration requires the following configuration parameters:

#### `subdomain` (Required)
Your Zendesk subdomain. For example, if your Zendesk URL is `https://mycompany.zendesk.com`, then your subdomain is `mycompany`.

#### `email` (Required)
Email address of the Zendesk user associated with the API token. This email must belong to a user with appropriate permissions to access the data you want to sync.

#### `api_token` (Required)
Zendesk API token for authentication. API tokens are preferred over basic authentication for security reasons.

**How to get your API token:**
1. Log in to your Zendesk account as an admin
2. Go to Admin Center → Apps and integrations → APIs → Zendesk API
3. Enable token access if not already enabled
4. Click "Add API token"
5. Copy the generated token

#### `timeout` (Optional)
Request timeout in seconds. Default is 30 seconds.

### Example Configuration

```yaml
subdomain: "mycompany"
email: "api-user@mycompany.com"  
api_token: "your-api-token-here"
timeout: 30
```

## Authentication

This integration uses **API token authentication**, which is the recommended authentication method for Zendesk integrations.

### API Token Format
The integration formats authentication as: `{email}/token:{api_token}` and uses HTTP Basic Authentication as required by Zendesk.

### Required Permissions
The API token user must have permissions to:
- View and manage tickets
- View and manage users
- View and manage organizations  
- Access side conversations (requires Collaboration add-on)

## Rate Limiting

The integration implements comprehensive rate limiting handling:

- **Automatic retry**: When rate limits are hit (HTTP 429), the integration automatically waits and retries
- **Concurrent requests**: Limited to 5 concurrent requests to respect API limits
- **Rate limit headers**: Monitors `Retry-After` headers for optimal retry timing

### Zendesk Rate Limits by Plan
- Team: 200 requests/minute
- Growth: 400 requests/minute  
- Professional: 400 requests/minute
- Enterprise: 700 requests/minute
- Enterprise Plus: 2500 requests/minute

## Supported Resources

### Tickets
- **Endpoint**: `/api/v2/tickets`
- **Data**: Full ticket details including status, priority, assignee, custom fields
- **Pagination**: Automatic handling of large ticket datasets
- **Webhooks**: Real-time updates for ticket events

### Side Conversations  
- **Endpoint**: `/api/v2/tickets/{ticket_id}/side_conversations`
- **Data**: Side conversation details with participant information
- **Note**: Requires Zendesk Collaboration add-on
- **Webhooks**: Updates when side conversations are modified

### Users
- **Endpoint**: `/api/v2/users`
- **Data**: User profiles including role, organization, custom fields
- **Types**: End-users, agents, administrators
- **Webhooks**: Real-time updates for user changes

### Organizations
- **Endpoint**: `/api/v2/organizations`
- **Data**: Organization details including domains, custom fields
- **Webhooks**: Real-time updates for organization changes

## Webhook Support

The integration supports real-time updates via Zendesk webhooks for:

### Ticket Events
- Ticket creation, updates, deletion
- Status and priority changes
- Assignee and group changes
- Comment additions
- Tag and custom field updates

### User Events  
- User creation, updates, deletion
- Role changes
- Status changes (active/suspended)
- Identity management events

### Organization Events
- Organization creation, updates, deletion
- Domain name changes
- Custom field updates

### Webhook Configuration
To enable real-time updates:
1. Create webhooks in Zendesk Admin Center
2. Point webhooks to your Ocean integration endpoint: `{your-ocean-url}/webhook`
3. Subscribe to relevant event types
4. Configure authentication if required

## Development and Testing

### Local Development
```bash
# Install dependencies
make install

# Run integration locally
make run

# Run tests
make test

# Format and lint code
make format
make lint
```

### Testing the Integration
The integration includes comprehensive tests:
- Unit tests for client functionality
- Webhook processor tests
- Integration smoke tests
- Mock data for reliable testing

### Debugging
Enable debug mode by running:
```bash
python debug.py
```

## API Documentation References

This integration is based on official Zendesk API documentation:

- [Zendesk API Reference](https://developer.zendesk.com/api-reference/introduction/introduction/)
- [Tickets API](https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/)
- [Side Conversations API](https://developer.zendesk.com/api-reference/ticketing/side_conversation/side_conversation/)
- [Users API](https://developer.zendesk.com/api-reference/ticketing/users/users/)
- [Organizations API](https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/)
- [Webhooks API](https://developer.zendesk.com/api-reference/webhooks/webhooks-api/webhooks/)
- [Rate Limits](https://developer.zendesk.com/api-reference/introduction/rate-limits/)
- [Authentication](https://developer.zendesk.com/api-reference/introduction/security-and-auth/)

## Troubleshooting

### Common Issues

#### Authentication Errors
- Verify API token is correct and not expired
- Ensure email matches the token owner
- Check that the user has required permissions

#### Rate Limiting
- Monitor your Zendesk plan's rate limits
- Consider upgrading if hitting limits frequently
- The integration automatically handles rate limiting with retries

#### Missing Data
- Verify user has access to all required resources
- Check if side conversations require Collaboration add-on
- Ensure webhook events are properly configured

#### Connection Issues
- Verify subdomain is correct
- Check network connectivity to Zendesk
- Ensure firewall allows outbound HTTPS connections

### Support
For integration-specific issues, please refer to the Port Ocean documentation and support channels.

## Contributing

This integration follows Ocean development guidelines:
- Use async/await patterns
- Implement proper error handling
- Follow Ocean testing patterns
- Maintain backward compatibility
- Document all changes in CHANGELOG.md

## License

This integration is part of the Port Ocean project and follows the same license terms.