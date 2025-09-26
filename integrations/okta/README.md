# Okta Integration

[![Slack](https://img.shields.io/badge/Slack-4A154B?style=for-the-badge&logo=slack&logoColor=white)](https://getport.io/community)

This integration allows you to import `users`, `groups`, `roles`, `permissions`, and `applications` from your Okta organization into Port.

## Overview

The Okta integration provides a comprehensive view of your identity and access management by importing:

- **Users** - Okta user accounts with profiles, status, and organizational information
- **Groups** - Okta groups with membership details and role assignments  
- **Roles** - Administrative and custom roles with associated permissions
- **Permissions** - Role assignments and access control definitions
- **Applications** - Integrated applications with user and group assignments

## Getting Started

### Requirements

- Okta domain (e.g., `dev-123456.okta.com`)
- Okta API token with appropriate permissions

### Okta API Token Setup

1. Log in to your Okta Admin Console
2. Navigate to **Security > API** 
3. Click **Tokens** tab
4. Click **Create Token**
5. Enter a descriptive name for the token
6. Click **Create Token**
7. Copy the token value (you won't be able to see it again)

### Required Permissions

Your API token needs the following scopes:
- `okta.users.read` - Read user information
- `okta.groups.read` - Read group information  
- `okta.roles.read` - Read role information
- `okta.apps.read` - Read application information
- `okta.iam.read` - Read identity and access management information

## Installation

To install the integration, run the following command in your terminal:

```bash
curl -L https://ocean.getport.io/initiator | bash
```

Follow the interactive installer and choose the Okta integration when prompted.

## Configuration

The integration uses the following configuration parameters:

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `okta_domain` | ✅ | String | Your Okta domain (e.g., `dev-123456.okta.com`) |
| `okta_api_token` | ✅ | String | Okta API token for authentication |

### Example Configuration

```yaml
# Integration configuration
okta_domain: "dev-123456.okta.com"
okta_api_token: "your-api-token-here"
```

## Blueprints

The integration creates the following blueprints:

### User Blueprint (`oktaUser`)

Represents an Okta user account with comprehensive profile information.

**Properties:**
- `id` - Unique user identifier
- `email` - User's email address  
- `status` - Account status (ACTIVE, DEPROVISIONED, etc.)
- `created` - Account creation date
- `activated` - Account activation date
- `displayName` - User's full display name
- `login` - User's login identifier
- `type` - User account type
- `locale` - User's locale setting
- `department` - User's department

**Relations:**
- `groups` - Groups the user belongs to
- `manager` - User's manager
- `roles` - Administrative roles assigned to the user

### Group Blueprint (`oktaGroup`)

Represents an Okta group with membership and role information.

**Properties:**
- `id` - Unique group identifier
- `name` - Group name
- `description` - Group description
- `type` - Group type (OKTA_GROUP, APP_GROUP, BUILT_IN)
- `created` - Group creation date
- `lastUpdated` - Last modification date
- `lastMembershipUpdated` - Last membership change date

**Relations:**
- `members` - Users who are members of the group
- `team` - Parent team or group
- `roles` - Roles assigned to the group

### Role Blueprint (`oktaRole`)

Represents administrative roles and permissions.

**Properties:**
- `id` - Unique role identifier
- `label` - Human-readable role name
- `type` - Role type (STANDARD, CUSTOM)
- `status` - Role status (ACTIVE, INACTIVE)
- `created` - Role creation date
- `lastUpdated` - Last modification date
- `description` - Role description

**Relations:**
- `permissions` - Permissions granted by this role

### Permission Blueprint (`oktaPermission`)

Represents role assignments and access permissions.

**Properties:**
- `id` - Unique permission assignment identifier
- `type` - Permission type (USER_ADMIN, GROUP_ADMIN, etc.)
- `status` - Assignment status (ACTIVE, INACTIVE)
- `created` - Assignment creation date
- `lastUpdated` - Last modification date
- `resource` - Resource the permission applies to

### Application Blueprint (`oktaApplication`)

Represents applications integrated with Okta.

**Properties:**
- `id` - Unique application identifier
- `name` - Application name
- `label` - Human-readable application label
- `status` - Application status (ACTIVE, INACTIVE)
- `created` - Application creation date
- `lastUpdated` - Last modification date
- `features` - Enabled application features
- `signOnMode` - Authentication method

**Relations:**
- `assignedUsers` - Users assigned to the application
- `assignedGroups` - Groups assigned to the application

## Advanced Configuration

### Filtering Data

You can filter the imported data using Okta's filter syntax:

```yaml
resources:
  - kind: oktaUser
    selector:
      filter: 'status eq "ACTIVE" and profile.department eq "Engineering"'
      limit: 100

  - kind: oktaGroup  
    selector:
      filter: 'type eq "OKTA_GROUP"'
      include_members: true
```

### Supported Filters

- **Users**: Filter by status, profile attributes, group membership
- **Groups**: Filter by type, name, description
- **Applications**: Filter by status, name, features

### Rate Limiting

The integration automatically handles Okta's rate limits by:
- Implementing exponential backoff on rate limit errors
- Using pagination to avoid large requests
- Respecting Okta's recommended request patterns

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify your API token is correct and hasn't expired
   - Ensure the token has the required permissions
   - Check that your Okta domain is correctly formatted

2. **Rate Limiting**
   - The integration automatically handles rate limits
   - If you experience consistent rate limiting, consider reducing the batch size

3. **Missing Data**
   - Check your API token permissions
   - Verify filters aren't excluding expected data
   - Review the integration logs for specific error messages

### Debug Mode

Enable debug logging to troubleshoot issues:

```yaml
# Add to your configuration
log_level: "DEBUG"
```

### Support

For support and questions:
- [Port Community Slack](https://getport.io/community)
- [Port Documentation](https://docs.getport.io/)
- [GitHub Issues](https://github.com/port-labs/ocean/issues)

## API Reference

### Okta REST API

This integration uses the following Okta REST API endpoints:

- `/api/v1/users` - User management
- `/api/v1/groups` - Group management  
- `/api/v1/iam/roles` - Role management
- `/api/v1/iam/roleAssignments` - Permission assignments
- `/api/v1/apps` - Application management

For more information, see the [Okta REST API documentation](https://developer.okta.com/docs/reference/).

## Examples

### Basic User Sync

```yaml
resources:
  - kind: oktaUser
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id
          title: .profile.displayName
          blueprint: oktaUser
          properties:
            email: .profile.email
            status: .status
            department: .profile.department
```

### Group with Members

```yaml  
resources:
  - kind: oktaGroup
    selector:
      query: 'true'
      include_members: true
    port:
      entity:
        mappings:
          identifier: .id
          title: .profile.name
          blueprint: oktaGroup
          relations:
            members: '[.members[].id] // []'
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](../../CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE.md) file for details.