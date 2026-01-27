# Harbor Integration

This integration syncs Harbor container registry data into Port, enabling platform and security teams to visualize images, projects, users, repositories, artifacts, and their relationships across the software supply chain.

## Features

- Sync Harbor projects, users, repositories, and artifacts into Port
- Real-time updates via Harbor webhooks
- Vulnerability scanning insights from Harbor's built-in scanner
- Configurable filters for projects and artifacts
- Support for both robot accounts and local user authentication
- Comprehensive relationship mapping between entities

## Configuration

The integration supports the following configuration options:

### Required Configuration

| Parameter | Type | Description |
|-----------|------|-------------|
| `harborHost` | string | Harbor instance URL (e.g., `http://localhost:8081` or `https://harbor.example.com`) |
| `harborUsername` | string | Harbor username (robot account recommended) |
| `harborPassword` | string | Harbor password or robot account token |

### Optional Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `verifySsl` | boolean | `true` | Verify SSL certificates when connecting to Harbor |
| `projectFilter.visibility` | string | `all` | Filter projects by visibility (`public`, `private`, `all`) |
| `projectFilter.namePrefix` | string | - | Filter projects by name prefix |
| `repositoryFilter.nameContains` | string | - | Filter repositories where name contains this string |
| `repositoryFilter.nameStartsWith` | string | - | Filter repositories where name starts with this prefix |
| `artifactFilter.minSeverity` | string | - | Only sync artifacts with vulnerability severity at or above this level (`negligible`, `low`, `medium`, `high`, `critical`) |
| `artifactFilter.tag` | string | - | Filter artifacts by tag name (exact match or pattern) |
| `artifactFilter.digest` | string | - | Filter artifacts by digest prefix |
| `artifactFilter.label` | string | - | Filter artifacts that have this label |
| `artifactFilter.mediaType` | string | - | Filter artifacts by media type |
| `artifactFilter.createdSince` | string | - | Filter artifacts created since this date (ISO 8601 format) |
| `webhookSecret` | string | - | Shared secret for webhook signature validation (optional but recommended) |

## Authentication

### Robot Account (Recommended)

Robot accounts are recommended for automated integrations:

1. In Harbor UI, go to Projects → Your Project → Robot Accounts
2. Click "New Robot Account"
3. Set permissions (at minimum: pull repository, read artifact, list artifact, list tag, list repository)
4. Copy the robot account name (format: `robot$project+name`) and token
5. Use the robot account name as `harborUsername` and token as `harborPassword`

### Local User

You can also use a local Harbor user account:

1. Use the username as `harborUsername`
2. Use the password as `harborPassword`

## Webhook Configuration

To enable real-time updates:

1. In Harbor UI, go to Projects → Your Project → Webhooks
2. Click "New Webhook"
3. Set the endpoint URL to your Ocean webhook endpoint
4. Select event types:
   - Push Artifact
   - Delete Artifact
   - Scanning Finished
   - Scanning Failed
5. (Optional) Set the auth header with your webhook secret for signature validation

## Entities

The integration creates the following Port entities:

### Harbor Project

Represents a Harbor project (namespace for repositories).

Properties:
- Owner name
- Public visibility flag
- Repository count
- Creation and update timestamps

### Harbor User

Represents a Harbor user account.

Properties:
- Email address
- Real name
- Admin role flag
- Creation and update timestamps

### Harbor Repository

Represents a container image repository.

Properties:
- Artifact count
- Pull count
- Description
- Creation and update timestamps

Relations:
- Belongs to a Harbor Project

### Harbor Artifact

Represents a container image artifact (specific version/tag).

Properties:
- Digest (SHA256)
- Size
- Tags list
- Labels list
- Push and pull timestamps
- Vulnerability scan status
- Scan severity
- Vulnerability counts by severity (Critical, High, Medium, Low)
- Total vulnerability count

Relations:
- Belongs to a Harbor Repository

## Example Configuration

```yaml
configurations:
  harborHost: http://localhost:8081
  harborUsername: robot$myproject+readonly
  harborPassword: eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
  verifySsl: true
  projectFilter:
    visibility: all
    namePrefix: prod-
  repositoryFilter:
    nameContains: app
    nameStartsWith: service
  artifactFilter:
    minSeverity: high
    tag: latest
    label: production
    createdSince: "2024-01-01T00:00:00Z"
  webhookSecret: my-secret-key
```

## Development

### Running Tests

```bash
poetry install
poetry run pytest
```

### Code Formatting

```bash
poetry run black .
```

## Support

For issues and questions, please open an issue in the [Ocean repository](https://github.com/port-labs/ocean/issues).
