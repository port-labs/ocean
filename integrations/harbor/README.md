# Harbor Integration

An Ocean integration for importing Harbor container registry resources into Port, supporting real-time webhook updates.

## Features

- **Resource Sync**: Import Harbor projects, users, repositories, and artifacts
- **Real-time Updates**: Webhook support for instant synchronization of changes
- **Filtering**: Configurable filters for projects, repositories, and artifacts
- **Security**: Robot account and local user authentication support
- **Vulnerability Scanning**: Integration with Harbor's security scanning features

## Supported Resources

- **Projects**: Harbor projects with visibility, ownership, and metadata
- **Users**: Harbor users with roles and permissions
- **Repositories**: Container repositories with artifact counts and metadata
- **Artifacts**: Container images with tags, digests, and vulnerability scan results

## Quick Start

### 1. Authentication Setup

#### Robot Account (Recommended)
```bash
# Create a robot account in Harbor with appropriate permissions
# Use robot name as username and token as password
export HARBOR_USERNAME="robot$project+robot-name"
export HARBOR_PASSWORD="your-robot-token"
```

**Note**: Harbor robot tokens expire after 30 days by default. When a token expires, the integration will log an error and stop functioning. To refresh a robot token:

1. Log in to Harbor as a system administrator
2. Navigate to "Robot Accounts" page
3. Select the expired robot account
4. Click "Action" → "Refresh Secret"
5. Update the integration configuration with the new token

#### Local User
```bash
# Use Harbor local user credentials
export HARBOR_USERNAME="your-username"
export HARBOR_PASSWORD="your-password"
```

### 2. Configuration

Create a `.env` file in the Harbor integration directory:

```bash
# Harbor API Configuration
HARBOR_HOST=http://localhost:8081
HARBOR_USERNAME=admin
HARBOR_PASSWORD=Harbor12345

# Robot Account Configuration (Alternative to username/password)
# HARBOR_ROBOT_NAME=robot$project+robot-name
# HARBOR_ROBOT_TOKEN=your-robot-token

# Webhook Configuration
WEBHOOK_SECRET=eI79zc...

# Port Configuration
PORT_BASE_URL=https://api.getport.io
PORT_CLIENT_ID=your-port-client-id
PORT_CLIENT_SECRET=your-port-client-secret
```

### 3. Webhook Setup (Optional)

For real-time updates, configure Harbor webhooks:

#### **Development Setup:**
1. Go to Harbor UI → **Administration** → **Interprojects** → **Webhooks**
2. Create webhook policy:
   - **Name**: `Port Ocean Integration`
   - **Target URL**: `http://localhost:8000/webhook`
   - **Event Types**: Select:
     - ✅ `PUSH_ARTIFACT`
     - ✅ `DELETE_ARTIFACT`
     - ✅ `SCANNING_COMPLETED`
     - ✅ `SCANNING_FAILED`
   - **Notification Type**: `HTTP`
   - **Payload Format**: `JSON`
   - **Skip Certificate Verification**: ✅ (for local development)

#### **Production Setup:**
1. Use your production Harbor instance
2. Set **Target URL**: `https://your-port-ocean-instance.com/webhook`
3. Configure **Authentication**:
   - **Auth Header**: `eI79zcCVK1ztqE7iphovDGaWaN70iIYbsOk7KsEcgzQ` (use the same secret from your .env file)
4. The `WEBHOOK_SECRET` is already configured in your `.env` file

## Resource Filtering

### Projects
```yaml
selector:
  name_prefix: "my-project"
  visibility: "public"  # or "private"
  owner: "admin"
```

### Repositories
```yaml
selector:
  project_name: "my-project"
  repository_name: "my-repo"
  label: "production"
```

### Artifacts
```yaml
selector:
  project_name: "my-project"
  repository_name: "my-repo"
  tag: "latest"
  severity_threshold: "High"  # "Low", "Medium", "High", "Critical"
  with_scan_overview: true
```

## Webhook Events

The integration supports these Harbor webhook events:

- **PUSH_ARTIFACT**: Artifact pushed to registry
- **PULL_ARTIFACT**: Artifact pulled from registry
- **DELETE_ARTIFACT**: Artifact deleted from registry
- **SCANNING_COMPLETED**: Vulnerability scan completed

## Development

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)
