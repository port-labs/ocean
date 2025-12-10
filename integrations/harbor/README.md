# Harbor Integration for Port

A production-ready Ocean integration that imports Harbor container registry resources (projects, repositories, artifacts, users) into Port's software catalog.

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Step-by-Step Setup](#step-by-step-setup)
- [Running Harbor Locally](#running-harbor-locally)
- [Configuration](#configuration)
- [Running the Integration](#running-the-integration)
- [Webhook Setup](#webhook-setup)
- [Blueprints & Mappings](#blueprints--mappings)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## Quick Start

### 🚀 Option 1: Automated Setup (Recommended)

Run the interactive quick-start script that will guide you through the entire setup:

```bash
cd integrations/harbor
./quick-start.sh
```

This script will:
- ✅ Check all prerequisites (Python, Poetry, Docker)
- ✅ Install dependencies
- ✅ Optionally set up Harbor locally
- ✅ Create environment variables file
- ✅ Push test data to Harbor
- ✅ Generate configuration file
- ✅ Run validation

### ⚡ Option 2: Manual Setup

For experienced users who already have Harbor and Port credentials:

```bash
# 1. Install dependencies
cd integrations/harbor
make install
source .venv/bin/activate

# 2. Set environment variables
export PORT_CLIENT_ID="your-port-client-id"
export PORT_CLIENT_SECRET="your-port-client-secret"
export HARBOR_ADMIN_USER="admin"
export HARBOR_ADMIN_PASS="Harbor12345"

# 3. Run the integration
ocean sail
```

## Prerequisites

Before you begin, ensure you have:

- **Python 3.12+** installed ([Download](https://www.python.org/downloads/))
- **Poetry 2.x** installed (`curl -sSL https://install.python-poetry.org | python3 -`)
- **Docker Desktop** installed and running ([Download](https://www.docker.com/products/docker-desktop/))
- **Git** installed
- **Port account** with API credentials ([Sign up free](https://app.getport.io))

## Step-by-Step Setup

### Step 1: Clone the Repository

```bash
# Clone the Ocean framework repository
git clone https://github.com/port-labs/ocean.git
cd ocean
```

### Step 2: Install Integration Dependencies

```bash
# Navigate to the Harbor integration directory
cd integrations/harbor

# Install dependencies using the Makefile
make install

# Activate the virtual environment
source .venv/bin/activate

# Verify installation
poetry show | grep port-ocean
```

### Step 3: Get Port API Credentials

1. Log in to [Port](https://app.getport.io)
2. Navigate to your **Builder** → **Settings** → **Credentials**
3. Copy your **Client ID** and **Client Secret**
4. Save them for the next step

### Step 4: Set Up Environment Variables

Create a `.env` file in the `integrations/harbor/` directory:

```bash
# Create .env file
cat > .env.local << 'EOF'
# Port API Credentials
PORT_CLIENT_ID=your-client-id-here
PORT_CLIENT_SECRET=your-client-secret-here

# Harbor Credentials (if using existing Harbor)
HARBOR_BASE_URL=http://localhost:8081/api/v2.0
HARBOR_ADMIN_USER=admin
HARBOR_ADMIN_PASS=Harbor12345

# Optional: Organization ID for multi-tenant logging
PORT_ORG_ID=my-organization
EOF

# Load environment variables
set -a
source .env.local
set +a
```

## Running Harbor Locally

If you don't have an existing Harbor instance, follow these steps to run Harbor locally using Docker:

### Step 1: Download Harbor Installer

```bash
# Create a directory for Harbor
mkdir -p ~/harbor-test && cd ~/harbor-test

# Download Harbor offline installer (v2.10.0 or later)
curl -LO https://github.com/goharbor/harbor/releases/download/v2.10.0/harbor-offline-installer-v2.10.0.tgz

# Extract the installer
tar xzvf harbor-offline-installer-v2.10.0.tgz
cd harbor
```

### Step 2: Configure Harbor

```bash
# Copy the template configuration
cp harbor.yml.tmpl harbor.yml

# Edit harbor.yml and set the following:
# - hostname: localhost
# - http.port: 8081
# - harbor_admin_password: Harbor12345
# - Comment out HTTPS section if not needed

# Quick configuration using sed
sed -i.bak 's/hostname: reg.mydomain.com/hostname: localhost/' harbor.yml
sed -i.bak 's/port: 80/port: 8081/' harbor.yml
sed -i.bak 's/harbor_admin_password: Harbor12345/harbor_admin_password: Harbor12345/' harbor.yml
```

### Step 3: Install and Start Harbor

```bash
# Run the installer with Trivy (for vulnerability scanning)
sudo ./install.sh --with-trivy

# Verify Harbor is running
docker compose ps

# You should see containers for:
# - harbor-core
# - harbor-portal
# - harbor-db
# - harbor-redis
# - harbor-jobservice
# - harbor-log
# - registry
# - trivy-adapter
```

### Step 4: Access Harbor UI

1. Open your browser and navigate to: **http://localhost:8081**
2. Log in with:
   - **Username:** `admin`
   - **Password:** `Harbor12345`

### Step 5: Create Test Data in Harbor

```bash
# Create a project via Harbor API
curl -X POST "http://localhost:8081/api/v2.0/projects" \
  -u "admin:Harbor12345" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "opensource",
    "metadata": {
      "public": "true"
    }
  }'

# Pull a test image
docker pull alpine:latest

# Tag it for Harbor
docker tag alpine:latest localhost:8081/opensource/alpine:latest

# Log in to Harbor registry
docker login localhost:8081 -u admin -p Harbor12345

# Push the image
docker push localhost:8081/opensource/alpine:latest

# Verify the push
curl -u "admin:Harbor12345" "http://localhost:8081/api/v2.0/projects/opensource/repositories"
```

### Step 6: Create a Robot Account (Recommended)

Robot accounts are the recommended way to authenticate for automation:

1. In Harbor UI, go to **Projects** → **opensource**
2. Navigate to **Robot Accounts** tab
3. Click **New Robot Account**
4. Configure:
   - **Name:** `port-sync`
   - **Expiration:** Never expires (or set your preference)
   - **Permissions:** Select all read permissions
5. Click **Add** and copy the generated token
6. Update your `.env.local`:

```bash
HARBOR_AUTH_MODE=robot_token
HARBOR_ROBOT_ACCOUNT=robot$opensource+port-sync
HARBOR_ROBOT_TOKEN=<paste-your-token-here>
```

## Configuration

### Create Your Configuration File

Create a `config.yaml` file in the `integrations/harbor/` directory. You can start from the sample:

```bash
# Copy the sample configuration
cp examples/config.sample.yaml config.yaml

# Edit config.yaml with your settings
nano config.yaml  # or use your preferred editor
```

### Configuration Options

Here's a complete configuration example with explanations:

```yaml
port:
  clientId: "{{ from env PORT_CLIENT_ID }}"
  clientSecret: "{{ from env PORT_CLIENT_SECRET }}"
  baseUrl: https://api.getport.io

eventListener:
  type: POLLING  # Use WEBHOOK for real-time updates (requires webhook setup)

integration:
  identifier: harbor-local
  type: Harbor
  config:
    # Harbor API endpoint (required)
    baseUrl: http://localhost:8081/api/v2.0

    # Authentication (choose one method)
    authMode: basic  # Options: basic, robot_token, oidc
    username: "{{ from env HARBOR_ADMIN_USER }}"
    password: "{{ from env HARBOR_ADMIN_PASS }}"

    # For robot account (recommended for production):
    # authMode: robot_token
    # robotAccount: "robot$opensource+port-sync"
    # robotToken: "{{ from env HARBOR_ROBOT_TOKEN }}"

    # Filtering options (all optional)
    projects: "opensource"  # Comma-separated list or array, empty = all projects
    projectVisibilityFilter: ["public", "private"]
    projectNamePrefix: ""

    repositoryProjectFilter: []
    repositoryNamePrefix: ""
    repositoryNameContains: ""

    artifactTagFilter: ""  # e.g., ["latest", "stable"]
    artifactDigestFilter: []
    artifactLabelFilter: []
    artifactMediaTypeFilter: []
    artifactCreatedSince: ""  # ISO 8601 format, e.g., "2024-01-01T00:00:00Z"
    artifactVulnSeverityAtLeast: ""  # Options: Critical, High, Medium, Low, Negligible

    # Performance tuning
    maxConcurrentRequests: 5
    maxRetries: 3
    retryJitterSeconds: 0.5

    # Logging
    logLevel: DEBUG  # Options: DEBUG, INFO, WARN, ERROR

    # Multi-tenant support
    portOrgId: "{{ from env PORT_ORG_ID }}"
```

### Configuration Sections Explained

#### Authentication Methods

**1. Basic Authentication** (simplest for testing):
```yaml
authMode: basic
username: "admin"
password: "Harbor12345"
```

**2. Robot Account** (recommended for production):
```yaml
authMode: robot_token
robotAccount: "robot$opensource+port-sync"
robotToken: "your-robot-token-here"
```

**3. OIDC** (for enterprise SSO):
```yaml
authMode: oidc
oidcAccessToken: "your-oidc-token"
```

#### Filtering Options

**Project Filters:**
- `projects`: Sync only specific projects (e.g., `["platform", "sre"]`)
- `projectVisibilityFilter`: Filter by visibility (`["public"]` or `["private"]`)
- `projectNamePrefix`: Only sync projects starting with this prefix

**Repository Filters:**
- `repositoryProjectFilter`: Only sync repositories from specific projects
- `repositoryNamePrefix`: Only sync repositories starting with this prefix (e.g., `"library/"`)
- `repositoryNameContains`: Only sync repositories containing this string

**Artifact Filters:**
- `artifactTagFilter`: Only sync artifacts with specific tags (e.g., `["latest", "stable"]`)
- `artifactDigestFilter`: Sync specific digests
- `artifactLabelFilter`: Sync artifacts with specific labels
- `artifactMediaTypeFilter`: Filter by media type
- `artifactCreatedSince`: Only sync artifacts created after this date
- `artifactVulnSeverityAtLeast`: Only sync artifacts with vulnerabilities at or above this severity

## Running the Integration

### Step 1: Set Up Port Blueprints

Before running the integration, you need to create the blueprints in Port:

```bash
# Install the Port CLI (if not already installed)
npm install -g @port-labs/port-cli

# Or use Python
pip install port-ocean

# Navigate to the blueprints directory
cd examples/blueprints

# Create each blueprint in Port
for blueprint in *.yaml; do
  echo "Creating blueprint from $blueprint"
  curl -X POST "https://api.getport.io/v1/blueprints" \
    -H "Authorization: Bearer $(curl -X POST https://api.getport.io/v1/auth/access_token \
      -H 'Content-Type: application/json' \
      -d "{\"clientId\": \"$PORT_CLIENT_ID\", \"clientSecret\": \"$PORT_CLIENT_SECRET\"}" | jq -r '.accessToken')" \
    -H "Content-Type: application/json" \
    -d @$blueprint
done
```

Or manually via Port UI:
1. Go to [Port Builder](https://app.getport.io/settings/data-model)
2. Click **+ Blueprint**
3. Copy-paste content from each file in `examples/blueprints/`
4. Import in this order:
   - `harbor_project.yaml`
   - `harbor_user.yaml`
   - `harbor_repository.yaml`
   - `harbor_artifact.yaml`

### Step 2: Test the Integration (Dry Run)

```bash
# Make sure you're in the harbor integration directory
cd integrations/harbor

# Activate virtual environment
source .venv/bin/activate

# Load environment variables
set -a && source .env.local && set +a

# Run a dry-run validation (doesn't write to Port)
ocean sail --validate

# You should see output like:
# ✓ harbor-project: 1 entities
# ✓ harbor-user: 2 entities
# ✓ harbor-repository: 1 entities
# ✓ harbor-artifact: 1 entities
```

### Step 3: Run Full Sync

Once validation looks good, run the actual sync:

```bash
# Run the integration
ocean sail

# Or run in the background
nohup ocean sail > harbor-integration.log 2>&1 &
```

### Step 4: Verify in Port

1. Go to [Port](https://app.getport.io)
2. Navigate to your **Software Catalog**
3. You should see new entities:
   - **Harbor Projects** (e.g., `opensource`)
   - **Harbor Repositories** (e.g., `opensource/alpine`)
   - **Harbor Artifacts** (e.g., `opensource/alpine@sha256:...`)
   - **Harbor Users** (e.g., `admin`)

### Step 5: Monitor Logs

The integration emits structured logs you can monitor:

```bash
# Watch logs in real-time
tail -f harbor-integration.log | grep harbor

# Filter specific events
tail -f harbor-integration.log | grep "harbor.resync"
tail -f harbor-integration.log | grep "harbor.webhook.processed"
```

## Webhook Setup (Optional - Real-Time Updates)

For real-time updates when images are pushed/scanned, configure webhooks:

### Step 1: Generate Webhook Secret

```bash
# Generate a random secret
WEBHOOK_SECRET=$(openssl rand -hex 32)
echo "WEBHOOK_SECRET=$WEBHOOK_SECRET" >> .env.local
echo "Your webhook secret: $WEBHOOK_SECRET"
```

### Step 2: Update Configuration

Edit your `config.yaml`:

```yaml
eventListener:
  type: WEBHOOK  # Change from POLLING

integration:
  config:
    webhookSecret: "{{ from env WEBHOOK_SECRET }}"
```

### Step 3: Expose Integration Endpoint

For local testing, use ngrok or similar:

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com

# Expose the integration (runs on port 8000 by default)
ngrok http 8000

# Note the public URL (e.g., https://abc123.ngrok.io)
```

### Step 4: Configure Harbor Webhook

1. Log in to Harbor UI at http://localhost:8081
2. Go to **Projects** → **opensource** → **Webhooks**
3. Click **+ NEW WEBHOOK**
4. Configure:
   - **Name:** `Port Integration`
   - **Notify Type:** `http`
   - **Event Type:** Check all:
     - ✓ Artifact pushed
     - ✓ Artifact deleted
     - ✓ Scanning completed
   - **Endpoint URL:** `https://your-ngrok-url.ngrok.io/webhook`
   - **Auth Header:** Leave empty
   - **Secret:** Paste your `WEBHOOK_SECRET`
5. Click **CONTINUE** → **TEST ENDPOINT** → **SAVE**

### Step 5: Test Webhook

```bash
# Push a new image to trigger webhook
docker tag alpine:latest localhost:8081/opensource/test-webhook:latest
docker push localhost:8081/opensource/test-webhook:latest

# Check integration logs
tail -f harbor-integration.log | grep webhook

# You should see:
# harbor.webhook.processed | event_type=PUSH_ARTIFACT | verified=true | updated_count=1
```

## Blueprints & Mappings

### Blueprint Relationships

The integration creates four interconnected blueprints:

```
harborProject
├── harborRepository (many)
│   └── harborArtifact (many)
└── harborUser (many, via membership)
```

### Import Blueprints

All blueprint definitions are in `examples/blueprints/`:

- **[harbor_project.yaml](examples/blueprints/harbor_project.yaml)** - Container projects
- **[harbor_user.yaml](examples/blueprints/harbor_user.yaml)** - Users and robot accounts
- **[harbor_repository.yaml](examples/blueprints/harbor_repository.yaml)** - Container repositories
- **[harbor_artifact.yaml](examples/blueprints/harbor_artifact.yaml)** - Container images with vulnerability data

### Apply Mappings

The mapping configuration (`examples/mappings.yaml`) defines how Harbor data maps to Port entities. It's automatically applied when you run the integration.

## Testing

### Run Unit Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
make test

# Or use pytest directly
poetry run pytest -v

# Run specific test file
poetry run pytest tests/test_webhook_handler.py -v

# Run with coverage
poetry run pytest --cov=. --cov-report=html
```

Expected output:
```
============================= test session starts ==============================
tests/test_client.py::test_robot_token_auth_header PASSED
tests/test_client.py::test_basic_auth_header PASSED
tests/test_client_pagination.py::test_iter_pages_streams_until_depleted PASSED
tests/test_webhook_handler.py::test_webhook_signature_valid PASSED
...
============================== 27 passed in 1.31s ===============================
```

### Manual Integration Test

```bash
# Test Harbor connectivity
curl -u "admin:Harbor12345" "http://localhost:8081/api/v2.0/projects"

# Test with the integration's client
python -c "
from integrations.harbor.client import HarborClient
import asyncio

async def test():
    client = HarborClient(
        'http://localhost:8081/api/v2.0',
        'basic',
        username='admin',
        password='Harbor12345'
    )
    response = await client.get('/projects')
    print(response.json())

asyncio.run(test())
"
```

## Troubleshooting

### Common Issues

#### 1. "Connection refused" Error

**Problem:** Can't connect to Harbor
```
harbor.http.request.transport_error | error=Connection refused
```

**Solution:**
- Verify Harbor is running: `docker compose ps` (should show 8+ containers)
- Check Harbor port: `curl http://localhost:8081/api/v2.0/projects`
- Verify `baseUrl` in config matches Harbor's API endpoint

#### 2. Authentication Failed

**Problem:** 401 Unauthorized
```
harbor.http.request.error | status=401
```

**Solution:**
- Verify credentials in `.env.local`
- For robot accounts, check the format: `robot$project+accountname`
- Test credentials: `curl -u "admin:Harbor12345" "http://localhost:8081/api/v2.0/projects"`

#### 3. No Entities Synced

**Problem:** Integration runs but no entities appear in Port
```
harbor.resync.done | count=0
```

**Solution:**
- Check filters in `config.yaml` - they might be too restrictive
- Verify projects exist in Harbor
- Run with `logLevel: DEBUG` to see detailed filtering logs
- Ensure blueprints are created in Port before running integration

#### 4. Webhook Signature Invalid

**Problem:** Webhooks are rejected
```
harbor.webhook.signature_mismatch | verified=false
```

**Solution:**
- Verify `webhookSecret` matches in both Harbor webhook config and integration config
- Check webhook endpoint URL is accessible from Harbor
- Test webhook manually using Harbor's "Test Endpoint" button

#### 5. Port API Rate Limiting

**Problem:** 429 Too Many Requests

**Solution:**
- Reduce `maxConcurrentRequests` in config (try 3 or lower)
- Add delays between resyncs
- Contact Port support for rate limit increase

### Debug Mode

Enable detailed logging:

```yaml
# In config.yaml
integration:
  config:
    logLevel: DEBUG
```

Run with verbose output:
```bash
ocean sail --debug
```

### Get Support

- **Integration Issues:** Open an issue at [port-labs/ocean](https://github.com/port-labs/ocean/issues)
- **Port Platform:** [Port Documentation](https://docs.getport.io)
- **Harbor Issues:** [goharbor/harbor](https://github.com/goharbor/harbor/issues)

## Advanced Configuration

### Performance Tuning

For large Harbor installations:

```yaml
integration:
  config:
    maxConcurrentRequests: 10  # Increase for faster syncs
    maxRetries: 3
    retryJitterSeconds: 0.5

    # Use filters to reduce data volume
    projects: ["prod", "staging"]  # Only sync specific projects
    artifactVulnSeverityAtLeast: "High"  # Only high/critical CVEs
```

### Multi-Environment Setup

Run separate integrations for different Harbor instances:

```yaml
# config.prod.yaml
integration:
  identifier: harbor-prod
  config:
    baseUrl: https://harbor.prod.company.com/api/v2.0

# config.staging.yaml
integration:
  identifier: harbor-staging
  config:
    baseUrl: https://harbor.staging.company.com/api/v2.0
```

### Scheduled Resyncs

Use cron or systemd timers:

```bash
# Add to crontab (sync every 6 hours)
0 */6 * * * cd /path/to/ocean/integrations/harbor && source .venv/bin/activate && ocean sail
```

## Next Steps

1. ✅ Set up blueprints in Port
2. ✅ Configure and test the integration
3. ✅ Set up webhooks for real-time updates
4. ✅ Create Port dashboards to visualize your container registry
5. ✅ Set up alerts for high-severity vulnerabilities
6. ✅ Integrate with your CI/CD pipeline

**Happy syncing!** 🚀
