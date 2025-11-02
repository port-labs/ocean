# Harbor Integration

Port's Harbor integration allows you to model Harbor container registry resources in your software catalog and ingest data into them.

---

## Overview

This integration allows you to:

* Import Harbor projects, users, repositories, and artifacts into Port in real-time.
* Watch for container image changes (pushes, deletions, scans) via webhooks and automatically sync them to your Port software catalog.
* Define automations and actions based on Harbor events and entities.
* Model your Harbor entities such as `project`, `user`, `repository`, and `artifact` as native Port resources with full relationship mapping.

---

## Supported Resources

The following Harbor resources can be ingested into Port:

| Harbor Resource | Port Kind      | Description                                      |
|-----------------|----------------|--------------------------------------------------|
| Projects        | `project`      | Harbor projects (public/private collections)     |
| Users           | `user`         | Harbor user accounts and administrators          |
| Repositories    | `repository`   | Container image repositories within projects     |
| Artifacts       | `artifact`     | Container images with tags and scan results      |

Each field available from the Harbor API v2.0 can be referenced in the integration's mapping configuration.

---

## Setup

### Prerequisites

* [Port account](https://app.port.io)
* Harbor instance (v2.0+) with API access
* Harbor admin credentials or robot account with appropriate permissions
* Python 3.13+ with `venv` (recommended)
* [Ocean CLI](https://ocean.getport.io/install-ocean/) installed

---

### Retrieving Harbor Credentials

To integrate with Harbor, you'll need authentication credentials:

#### Option 1: Using Admin Account (Development)

1. **Access Harbor UI**: Navigate to your Harbor instance (e.g., `http://localhost:8081`)
2. **Login**: Use your admin credentials (default: `admin` / `Harbor12345`)
3. **Use credentials directly**: Username: `admin`, Password: your admin password

#### Option 2: Using Robot Account (Recommended for Production)

1. **Access Harbor UI**: Navigate to your Harbor instance
2. **Navigate to Robot Accounts**: Go to `Administration` → `Robot Accounts`
3. **Create New Robot Account**:
   * Click `+ NEW ROBOT ACCOUNT`
   * Name: `port-ocean-integration`
   * Expiration: Set appropriate expiration (or never)
   * Permissions: Grant at least `Pull` permissions for all projects
4. **Save Credentials**:
   * Copy the robot account name (e.g., `robot$port-ocean-integration`)
   * Copy the generated token
   * **Important**: Store these securely - the token is only shown once

---

### Environment Variables

You'll need to configure the following environment variables:

```env
# Port Configuration
OCEAN__PORT__CLIENT_ID=<your_port_client_id>
OCEAN__PORT__CLIENT_SECRET=<your_port_client_secret>

# Harbor Configuration
OCEAN__INTEGRATION__CONFIG__HARBOR_URL=http://localhost:8081
OCEAN__INTEGRATION__CONFIG__USERNAME=admin
OCEAN__INTEGRATION__CONFIG__PASSWORD=Harbor12345

# Optional: For webhook support
OCEAN__INTEGRATION__CONFIG__WEBHOOK_SECRET=<your_webhook_secret>
OCEAN__INTEGRATION__CONFIG__APP_HOST=https://<your-domain>.com
```

---

### Installation

#### Local Development

1. **Create and activate a virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install the integration**:

   ```bash
   pip install "port-ocean[cli]"
   ```

3. **Set up the integration**:

   ```bash
   ocean new
   # Follow prompts to configure Harbor integration
   ```

4. **Configure environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env with your Harbor and Port credentials
   ```

5. **Start the integration**:

   ```bash
   ocean sail goharbor
   ```

You should see logs indicating successful startup and data synchronization.

---

## Configuration

The integration configuration is defined in `.port/spec.yaml`:

```yaml
type: goharbor
description: GoHarbor container registry integration for Port Ocean
icon: Harbor
docs: https://github.com/goharbor/harbor

features:
  - type: exporter
    section: Container Registry
    resources:
      - kind: project
      - kind: user
      - kind: repository
      - kind: artifact

configurations:
  - name: harborUrl
    required: true
    type: url
    description: "The URL of your Harbor instance (e.g., http://localhost:8081)"
    sensitive: false

  - name: username
    required: true
    type: string
    description: "Harbor username (admin user or robot account name)"
    sensitive: true

  - name: password
    required: true
    type: string
    description: "Harbor password or robot account token"
    sensitive: true

  - name: webhookSecret
    required: false
    type: string
    description: "Optional shared secret for validating Harbor webhook requests"
    sensitive: true
```

---

## Resource Mapping

### Default Blueprints

The integration creates the following blueprints in Port:

#### Harbor Project
```json
{
  "identifier": "harborProject",
  "title": "Harbor Project",
  "icon": "Harbor",
  "schema": {
    "properties": {
      "projectId": "number",
      "ownerName": "string",
      "public": "boolean",
      "repoCount": "number",
      "creationTime": "string (date-time)",
      "updateTime": "string (date-time)"
    }
  }
}
```

#### Harbor User
```json
{
  "identifier": "harborUser",
  "title": "Harbor User",
  "icon": "User",
  "schema": {
    "properties": {
      "userId": "number",
      "username": "string",
      "email": "string (email)",
      "realname": "string",
      "admin": "boolean",
      "creationTime": "string (date-time)",
      "updateTime": "string (date-time)"
    }
  }
}
```

#### Harbor Repository
```json
{
  "identifier": "harborRepository",
  "title": "Harbor Repository",
  "icon": "Docker",
  "schema": {
    "properties": {
      "repositoryId": "number",
      "name": "string",
      "artifactCount": "number",
      "pullCount": "number",
      "creationTime": "string (date-time)",
      "updateTime": "string (date-time)"
    }
  },
  "relations": {
    "project": "harborProject"
  }
}
```

#### Harbor Artifact
```json
{
  "identifier": "harborArtifact",
  "title": "Harbor Artifact",
  "icon": "Package",
  "schema": {
    "properties": {
      "digest": "string",
      "tags": "array",
      "size": "number",
      "pushTime": "string (date-time)",
      "scanOverview": "object"
    }
  },
  "relations": {
    "repository": "harborRepository",
    "project": "harborProject"
  }
}
```

### Customizing Mappings

You can customize the data mapping in `.port/resources/port-app-config.yml`:

```yaml
resources:
  - kind: artifact
    selector:
      query: "true"
      withScanOverview: true
      withTag: true
    port:
      entity:
        mappings:
          identifier: .digest
          title: .tags[0].name // (.digest | split(":")[1] | .[0:12])
          blueprint: '"harborArtifact"'
          properties:
            digest: .digest
            tags: '[.tags[]?.name] // []'
            size: .size
            scanOverview: .scan_overview
          relations:
            repository: .repository_id | tostring
            project: .project_id | tostring
```

---

## Webhook Support

This integration supports real-time updates via Harbor webhooks for the following events:

| Event Type                 | Description                                    |
|----------------------------|------------------------------------------------|
| `harbor.artifact.pushed`   | A new container image was pushed               |
| `harbor.artifact.deleted`  | A container image was deleted                  |
| `harbor.artifact.pulled`   | A container image was pulled                   |
| `harbor.scan.completed`    | Vulnerability scan completed                   |
| `harbor.scan.failed`       | Vulnerability scan failed                      |

### Setting Up Webhooks

Webhooks are automatically configured when the integration starts. You can also manually configure them:

1. **Navigate to Project Webhooks**: In Harbor UI, go to your project → `Webhooks`
2. **Create New Webhook**:
   * **Name**: `Port Ocean Integration`
   * **Notify Type**: `http`
   * **Event Types**: Select all artifact-related events
   * **Endpoint URL**: `https://your-domain.com/integration/webhook`
   * **Auth Header** (optional): Your webhook secret
3. **Test**: Push or pull an image to trigger the webhook

Webhook requests are sent to:

```
POST https://your-domain.com/integration/webhook
```

---

## Filtering and Selectors

The integration supports extensive filtering options:

### Project Filtering

```yaml
resources:
  - kind: project
    selector:
      query: "true"
      public: true          # Only public projects
      name: "prod-*"        # Projects starting with "prod-"
```

### Repository Filtering

```yaml
resources:
  - kind: repository
    selector:
      query: "true"
      projectName: "production"        # Specific project
      nameContains: "backend"          # Repos containing "backend"
      nameStartsWith: "service-"       # Repos starting with "service-"
```

### Artifact Filtering

```yaml
resources:
  - kind: artifact
    selector:
      query: "true"
      tag: "latest"                    # Specific tag
      withScanOverview: true           # Include scan results
      withTag: true                    # Include tag information
```

---

## Advanced Configuration

### Multi-Project Syncing

To sync artifacts from multiple projects efficiently:

```yaml
resources:
  - kind: artifact
    selector:
      query: '.project_id in [1, 2, 5]'  # Only specific projects
      withScanOverview: true
```

### Vulnerability Filtering

Filter artifacts based on vulnerability severity:

```yaml
resources:
  - kind: artifact
    selector:
      query: '.scan_overview."application/vnd.security.vulnerability.report; version=1.1".severity == "High"'
```

---

## Development

To develop or debug this integration:

1. **Clone the repository and install in editable mode**:

   ```bash
   git clone https://github.com/port-labs/ocean.git
   cd ocean/integrations/goharbor
   make install
   ```

2. **Set required environment variables**:

   ```bash
   export OCEAN__PORT__CLIENT_ID=your_client_id
   export OCEAN__PORT__CLIENT_SECRET=your_client_secret
   export OCEAN__INTEGRATION__CONFIG__HARBOR_URL=http://localhost:8081
   export OCEAN__INTEGRATION__CONFIG__USERNAME=admin
   export OCEAN__INTEGRATION__CONFIG__PASSWORD=Harbor12345
   ```

3. **Run tests**:

   ```bash
   pytest tests/ -v
   ```

4. **Start the integration**:

   ```bash
   ocean sail goharbor
   ```

5. **Simulate webhook events** (optional):

   ```bash
   curl -X POST http://localhost:8000/integration/webhook \
     -H "Content-Type: application/json" \
     -d @tests/fixtures/artifact_pushed.json
   ```

---

## Troubleshooting

### Common Issues

#### Authentication Failed

**Error**: `401 Unauthorized`

**Solution**: 
* Verify your Harbor credentials are correct
* Check that robot account has necessary permissions
* Ensure Harbor URL includes the correct protocol (http/https)

#### Webhooks Not Received

**Error**: Webhook events not triggering updates

**Solution**:
* Verify `app_host` is configured correctly
* Check webhook configuration in Harbor UI
* Ensure your Harbor instance can reach the integration endpoint
* Check Harbor webhook logs for delivery failures

#### Rate Limiting

**Error**: Too many API requests

**Solution**:
* The integration includes built-in rate limiting (5 concurrent requests)
* Adjust `MAX_CONCURRENT_REQUESTS` in `client.py` if needed
* Consider filtering to reduce the number of resources synced

#### Missing Scan Results

**Error**: `scanOverview` is empty

**Solution**:
* Ensure vulnerability scanning is enabled in Harbor
* Check that images have been scanned at least once
* Set `withScanOverview: true` in artifact selector

### Debugging

Enable verbose logging:

```bash
export LOG_LEVEL=DEBUG
ocean sail goharbor
```

Check integration logs:

```bash
# View real-time logs
tail -f logs/integration.log

# Search for errors
grep ERROR logs/integration.log
```

---

## Examples

### Use Case: Track Production Container Vulnerabilities

```yaml
resources:
  - kind: artifact
    selector:
      query: '.projectName == "production" and .tags[].name == "latest"'
      withScanOverview: true
    port:
      entity:
        mappings:
          identifier: .digest
          title: .tags[0].name
          blueprint: '"harborArtifact"'
          properties:
            vulnerabilityCount: '.scan_overview."application/vnd.security.vulnerability.report; version=1.1".summary.total'
            highSeverityCount: '.scan_overview."application/vnd.security.vulnerability.report; version=1.1".summary.summary.High'
```

### Use Case: Monitor Repository Activity

Track pull counts and last update times:

```yaml
resources:
  - kind: repository
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id | tostring
          title: .name
          blueprint: '"harborRepository"'
          properties:
            pullCount: .pull_count
            lastUpdated: .update_time
            isActive: '(.update_time | fromdateiso8601) > (now - 2592000)'  # Updated in last 30 days
```

---

## Performance Considerations

* **Pagination**: The integration automatically handles pagination (100 items per page)
* **Caching**: Frequently accessed data (projects, repositories) is cached during resyncs
* **Parallel Fetching**: Artifacts are fetched in parallel across repositories
* **Rate Limiting**: Built-in semaphore limits concurrent requests to 5

For large Harbor installations (1000+ artifacts):
* Consider using more specific filters in selectors
* Run resyncs during off-peak hours
* Monitor integration resource usage

---

## Related Links

* [Ocean SDK Documentation](https://ocean.getport.io)
* [Harbor API Reference](https://goharbor.io/docs/latest/working-with-projects/working-with-images/pulling-pushing-images/)
* [Port Integration Documentation](https://docs.port.io)
* [Harbor Documentation](https://goharbor.io/docs/)

---

## Support

For issues, questions, or contributions:

* **Issues**: [GitHub Issues](https://github.com/port-labs/ocean/issues)
* **Discussions**: [Port Community](https://github.com/port-labs/ocean/discussions)
* **Documentation**: [Port Docs](https://docs.port.io)

---

## License

This integration is part of the Port Ocean framework and is licensed under the same terms.