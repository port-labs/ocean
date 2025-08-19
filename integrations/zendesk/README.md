# Zendesk Integration

This integration brings information from Zendesk into Port, enabling you to track and manage your customer support operations alongside your other development and infrastructure resources.

## Features

- **Real-time synchronization**: Automatically sync Zendesk data to Port using webhooks
- **Comprehensive entity support**: Sync tickets, users, organizations, groups, and brands
- **Flexible authentication**: Support for both API tokens and OAuth
- **Advanced filtering**: Configure which data to sync using detailed selectors
- **Rate limiting**: Built-in handling of Zendesk API rate limits

## Prerequisites

- Zendesk instance (subdomain.zendesk.com)
- One of the following authentication methods:
  - **API Token**: Zendesk email + API token (recommended for server-to-server)
  - **OAuth Token**: OAuth access token (required for multi-customer applications)

## Configuration

### Authentication

You can authenticate using either an API token or OAuth token:

**Option 1: API Token Authentication (Recommended)**
```yaml
config:
  zendesk_subdomain: "your-subdomain"  # Without .zendesk.com
  zendesk_email: "your-email@company.com"
  zendesk_token: "your-api-token"
```

**Option 2: OAuth Token Authentication**
```yaml
config:
  zendesk_subdomain: "your-subdomain"  # Without .zendesk.com
  zendesk_oauth_token: "your-oauth-token"
```

### Resources

The integration supports the following resources:

#### Tickets
```yaml
resources:
  - kind: ticket
    selector:
      status: "open"              # Filter by status: new, open, pending, hold, solved, closed
      priority: "high"            # Filter by priority: low, normal, high, urgent
      assigneeId: 12345           # Filter by assignee user ID
      organizationId: 67890       # Filter by organization ID
```

#### Users
```yaml
resources:
  - kind: user
    selector:
      role: "agent"               # Filter by role: end-user, agent, admin
      organizationId: 67890       # Filter by organization ID
```

#### Organizations
```yaml
resources:
  - kind: organization
    selector:
      externalId: "org-123"       # Filter by external ID
```

#### Groups
```yaml
resources:
  - kind: group
    selector:
      includeDeleted: false       # Include deleted groups (default: false)
```

#### Brands
```yaml
resources:
  - kind: brand
    selector:
      activeOnly: true            # Only sync active brands (default: true)
```

## Getting Started

1. **Obtain Zendesk Credentials**
   - For API Token: Go to Zendesk Admin → APIs → Settings → Add API token
   - For OAuth: Create an OAuth application in your Zendesk instance

2. **Configure the Integration**
   - Set your Zendesk subdomain (e.g., "mycompany" for mycompany.zendesk.com)
   - Provide either email/token or OAuth token
   - Configure which resources to sync

3. **Set Up Webhooks** (Optional, for real-time updates)
   - The integration will automatically create webhooks when started
   - Webhooks provide real-time updates for tickets, users, and organizations
   - Requires admin permissions in Zendesk

## Supported Entities

### Tickets
- **Description**: Customer support tickets
- **Key Fields**: subject, status, priority, assignee, organization, tags, description
- **Real-time Updates**: ✅ (via webhooks)

### Users
- **Description**: Zendesk users (customers, agents, admins)
- **Key Fields**: name, email, role, organization, active status, verification status
- **Real-time Updates**: ✅ (via webhooks)

### Organizations
- **Description**: Customer organizations
- **Key Fields**: name, external ID, domain names, details
- **Real-time Updates**: ✅ (via webhooks)

### Groups
- **Description**: Agent groups for organizing support teams
- **Key Fields**: name, deleted status, creation/update dates
- **Real-time Updates**: ❌

### Brands
- **Description**: Zendesk brands for multi-brand instances
- **Key Fields**: name, brand URL, help center status, active status
- **Real-time Updates**: ❌

## Authentication Methods

### API Token (Recommended)
- **Use case**: Server-to-server integrations, single Zendesk instance
- **Setup**: Generate in Zendesk Admin → APIs → Settings
- **Security**: More secure than password authentication
- **Format**: email/token:api_token (automatically handled by the client)

### OAuth Token
- **Use case**: Multi-customer applications, distributed integrations
- **Setup**: Create OAuth application in Zendesk
- **Security**: Scoped permissions, easily revocable
- **Format**: Bearer token authentication

## Rate Limiting

The integration automatically handles Zendesk's rate limits:
- Respects `Retry-After` headers
- Implements concurrent request limiting
- Provides detailed logging for rate limit events

## Error Handling

- **Authentication errors**: Clear error messages for invalid credentials
- **API errors**: Comprehensive error logging with HTTP status codes
- **Network errors**: Automatic retry logic for transient failures
- **Data validation**: Validates webhook payloads and API responses

## Troubleshooting

### Common Issues

**Authentication Failed (401)**
- Verify your email and API token are correct
- For OAuth: Check that your token hasn't expired
- Ensure your user has appropriate permissions

**Missing Data**
- Check your selector filters - they might be too restrictive
- Verify your Zendesk user has access to the data you're trying to sync

**Webhooks Not Working**
- Ensure the integration user has admin permissions in Zendesk
- Check that webhook creation isn't blocked by firewall rules
- Verify the webhook endpoint is publicly accessible

### Debug Mode

Enable debug logging to troubleshoot issues:
```yaml
config:
  log_level: "DEBUG"
```

## API Reference

### Zendesk API Endpoints Used

- `GET /api/v2/tickets.json` - List tickets
- `GET /api/v2/users.json` - List users  
- `GET /api/v2/organizations.json` - List organizations
- `GET /api/v2/groups.json` - List groups
- `GET /api/v2/brands.json` - List brands
- `POST /api/v2/webhooks.json` - Create webhooks
- Individual resource endpoints for real-time updates

### Rate Limits

Zendesk enforces the following rate limits:
- **API requests**: 700 requests per minute per IP
- **Concurrent requests**: 5 simultaneous requests
- **Webhooks**: No specific limits, but subject to overall API limits

The integration automatically handles these limits with:
- Request queuing and throttling
- Automatic retry with exponential backoff
- Respect for `Retry-After` headers

## Contributing

To contribute to this integration:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `make test`
6. Submit a pull request

## License

This integration is licensed under the same terms as the Port Ocean framework.