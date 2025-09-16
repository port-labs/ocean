# Okta Integration

This integration brings information from Okta into Port, allowing you to sync users, groups, and applications from your Okta organization.

## Features

- **Users**: Sync Okta users with their profile information, status, and relationships
- **Groups**: Sync Okta groups with their members and metadata
- **Applications**: Sync Okta applications with their configuration and status
- **Live Events**: Real-time updates via Okta Event Hooks with webhook processors for immediate synchronization

## Configuration

### Required Configuration

- `okta_domain`: Your Okta domain (e.g., `dev-123456.okta.com`)
- `okta_api_token`: Your Okta API token with appropriate permissions

### API Token Permissions

Your Okta API token needs the following permissions:
- `okta.users.read` - To read user information
- `okta.groups.read` - To read group information  
- `okta.apps.read` - To read application information

## Data Model

### Okta Users

**Properties:**
- `id`: Unique user identifier
- `email`: User's email address
- `status`: User status (ACTIVE, DEPROVISIONED, LOCKED_OUT, etc.)
- `created`: Creation timestamp
- `department`: User's department
- `displayName`: User's display name
- `login`: User's login identifier
- `type`: User type
- `activated`: Activation timestamp
- `firstName`: User's first name
- `lastName`: User's last name
- `lastLogin`: Last login timestamp
- `lastUpdated`: Last update timestamp

**Relations:**
- `groups`: Many-to-many relationship with Okta groups
- `manager`: One-to-one relationship with another Okta user
- `applications`: Many-to-many relationship with Okta applications

### Okta Groups

**Properties:**
- `id`: Unique group identifier
- `name`: Group name
- `description`: Group description
- `type`: Group type (APP_GROUP, BUILT_IN, OKTA_GROUP)
- `created`: Creation timestamp
- `lastUpdated`: Last update timestamp
- `lastMembershipUpdated`: Last membership update timestamp

### Okta Applications

**Properties:**
- `id`: Unique application identifier
- `name`: Application name
- `label`: Application label
- `signOnMode`: Sign-on mode (AUTO_LOGIN, SAML_2_0, etc.)
- `status`: Application status (ACTIVE, DELETED, INACTIVE)
- `created`: Creation timestamp
- `lastUpdated`: Last update timestamp
- `features`: Application features


## Usage

1. Configure your Okta domain and API token in the integration settings
2. The integration will automatically sync users, groups, and applications
3. View the synced data in your Port workspace

## Live Events

The integration supports real-time updates through Okta Event Hooks. When the integration starts, it automatically:

1. **Creates Event Hooks**: Sets up Okta event hooks for user, group, and application lifecycle events
2. **Registers Webhook Processors**: Registers webhook processors to handle incoming events
3. **Processes Events**: Automatically updates Port when resources change in Okta

### Supported Events

- **User Events**: Create, update, delete, activate, deactivate, suspend, unsuspend, password changes
- **Group Events**: Create, update, delete, membership changes
- **Application Events**: Create, update, delete, user assignments

### Webhook Architecture

The integration uses a simple webhook processor pattern similar to Snyk:

- **Base Processor**: `OktaBaseWebhookProcessor` provides common functionality
- **Resource Processors**: Dedicated processors for users, groups, and applications
- **Direct Registration**: Webhook processors are registered directly in main.py
- **Event Validation**: Validates incoming events and extracts resource IDs
- **Automatic Updates**: Fetches current resource data and updates Port

## Development

### Running Tests

```bash
poetry install
poetry run pytest

# Run specific test files
poetry run pytest tests/test_okta_client.py
poetry run pytest tests/test_webhook_processors.py
```

### Code Quality

```bash
poetry run black .
poetry run ruff check .
poetry run mypy .
```

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)