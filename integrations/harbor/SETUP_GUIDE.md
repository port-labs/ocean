# Harbor Integration Setup Guide

## Visual Setup Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    SETUP OVERVIEW                            │
└─────────────────────────────────────────────────────────────┘

Step 1: Prerequisites                 ✓ Check Requirements
├── Python 3.12+                      ├── python3 --version
├── Poetry 2.x                        ├── poetry --version
├── Docker Desktop                    └── docker --version
└── Port Account

Step 2: Clone & Install               ✓ Setup Environment
├── git clone ocean repo
├── cd integrations/harbor
├── make install                      Creates .venv with dependencies
└── source .venv/bin/activate

Step 3: Harbor Setup                  ✓ Container Registry
├── Option A: Use Existing Harbor
│   └── Get credentials from admin
└── Option B: Run Harbor Locally
    ├── Download installer (v2.10.0+)
    ├── Configure (hostname, port)
    ├── Install with Trivy
    └── Access at localhost:8081

Step 4: Port Setup                    ✓ Create Blueprints
├── Get API credentials
├── Create 4 blueprints:
│   ├── harborProject
│   ├── harborUser
│   ├── harborRepository
│   └── harborArtifact
└── Note: Relations connect them

Step 5: Configure Integration         ✓ Setup Config
├── Create .env.local
│   ├── PORT_CLIENT_ID
│   ├── PORT_CLIENT_SECRET
│   ├── HARBOR_BASE_URL
│   └── HARBOR credentials
├── Copy config.sample.yaml
└── Edit filters as needed

Step 6: Create Test Data              ✓ Populate Harbor
├── Create project in Harbor
├── Push test image (alpine)
└── Verify in Harbor UI

Step 7: Run Integration               ✓ Execute Sync
├── ocean sail --validate             Dry run
├── ocean sail                        Full sync
└── Check Port catalog

Step 8: Setup Webhooks (Optional)     ✓ Real-time Updates
├── Generate webhook secret
├── Configure Harbor webhook
├── Update eventListener type
└── Test with push event
```

## Quick Command Reference

### One-Line Automated Setup
```bash
./quick-start.sh
```

### Manual Setup Commands
```bash
# Install
make install && source .venv/bin/activate

# Configure
cp examples/config.sample.yaml config.yaml
nano config.yaml  # Edit with your settings

# Test
ocean sail --validate

# Run
ocean sail

# Background
nohup ocean sail > harbor.log 2>&1 &
```

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    DATA FLOW DIAGRAM                          │
└──────────────────────────────────────────────────────────────┘

Harbor Instance                       Ocean Integration
─────────────────                     ──────────────────
┌─────────────────┐                   ┌──────────────────┐
│   Projects      │────GET────────────▶│ ProjectsExporter │
│   Users         │                   │ UsersExporter    │
│   Repositories  │                   │ RepositoriesExp  │
│   Artifacts     │                   │ ArtifactsExporter│
└─────────────────┘                   └──────────────────┘
        │                                      │
        │ webhooks                             │ maps to
        ▼                                      ▼
┌─────────────────┐                   ┌──────────────────┐
│ Webhook Events  │────POST───────────▶│ WebhookHandler   │
│ • PUSH_ARTIFACT │                   │ (with signature  │
│ • DELETE        │                   │  validation)     │
│ • SCAN_COMPLETE │                   └──────────────────┘
└─────────────────┘                            │
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │  Port Catalog    │
                                      │                  │
                                      │  • Projects      │
                                      │  • Users         │
                                      │  • Repositories  │
                                      │  • Artifacts     │
                                      └──────────────────┘
```

## Component Responsibilities

```
┌──────────────────────────────────────────────────────────────┐
│                    COMPONENT DIAGRAM                          │
└──────────────────────────────────────────────────────────────┘

client.py (366 lines)
├── Async HTTP client wrapping port_ocean.utils.http_async_client
├── Authentication (robot, basic, OIDC)
├── Retry logic with exponential backoff
├── Pagination with caching
└── Structured logging

exporters/ (4 files, ~870 lines)
├── projects.py       - Fetches & filters projects
├── users.py          - Fetches users with memberships
├── repositories.py   - Fetches repos per project
└── artifacts.py      - Parallel artifact fetching

mappers/ (4 files, ~400 lines)
├── projects.py       - Maps to Port harborProject
├── users.py          - Maps to Port harborUser
├── repositories.py   - Maps to Port harborRepository
└── artifacts.py      - Maps to Port harborArtifact

webhooks/handler.py (268 lines)
├── Event validation
├── HMAC signature verification
├── Delta update processing
└── Structured event logging

integration.py (191 lines)
├── Configuration management
├── Settings validation
├── Client factory
└── Runtime context

main.py (293 lines)
├── Resync handlers for all kinds
├── Orchestrates exporters
└── Logging & metrics
```

## Testing Strategy

```
┌──────────────────────────────────────────────────────────────┐
│                    TEST COVERAGE                              │
└──────────────────────────────────────────────────────────────┘

Unit Tests (27 tests)
├── test_client.py
│   ├── Authentication methods
│   ├── Retry logic
│   ├── Backoff calculations
│   └── Semaphore usage
│
├── test_client_pagination.py
│   ├── Multi-page iteration
│   ├── Empty page handling
│   └── Max pages limit
│
├── test_*_exporter.py (4 files)
│   ├── Data transformation
│   ├── Filtering logic
│   └── Streaming behavior
│
├── test_mappers.py
│   ├── Field mapping
│   ├── Default values
│   └── Relationships
│
├── test_webhook_handler.py
│   ├── Signature validation
│   ├── Event processing
│   └── Organization ID logging
│
└── test_logging.py
    ├── Log context tracking
    └── Resync summaries

Integration Tests (manual)
├── Harbor connectivity
├── Authentication
├── Full resync
└── Webhook delivery
```

## Configuration Examples

### Minimal Configuration
```yaml
# For quick testing
port:
  clientId: "{{ from env PORT_CLIENT_ID }}"
  clientSecret: "{{ from env PORT_CLIENT_SECRET }}"

integration:
  identifier: harbor-test
  type: Harbor
  config:
    baseUrl: http://localhost:8081/api/v2.0
    authMode: basic
    username: admin
    password: Harbor12345
```

### Production Configuration
```yaml
# For production use
port:
  clientId: "{{ from env PORT_CLIENT_ID }}"
  clientSecret: "{{ from env PORT_CLIENT_SECRET }}"

eventListener:
  type: WEBHOOK

integration:
  identifier: harbor-prod
  type: Harbor
  config:
    baseUrl: https://harbor.company.com/api/v2.0
    authMode: robot_token
    robotAccount: "robot$infra+port-sync"
    robotToken: "{{ from env HARBOR_ROBOT_TOKEN }}"
    webhookSecret: "{{ from env WEBHOOK_SECRET }}"

    # Filters
    projects: ["production", "staging"]
    artifactVulnSeverityAtLeast: "High"

    # Performance
    maxConcurrentRequests: 10
    maxRetries: 5

    # Logging
    logLevel: INFO
    portOrgId: "{{ from env PORT_ORG_ID }}"
```

### Security-Focused Configuration
```yaml
# Only sync critical security data
integration:
  config:
    # Limit scope
    projects: ["production"]
    projectVisibilityFilter: ["private"]

    # Only images with vulnerabilities
    artifactVulnSeverityAtLeast: "Critical"

    # Recent images only
    artifactCreatedSince: "2024-01-01T00:00:00Z"

    # Limit data volume
    maxConcurrentRequests: 3
```

## Troubleshooting Decision Tree

```
Start: Integration not working
│
├─▶ Can't connect to Harbor?
│   ├─▶ Check Harbor is running: docker compose ps
│   ├─▶ Check baseUrl in config matches Harbor API
│   └─▶ Test: curl http://localhost:8081/api/v2.0/projects
│
├─▶ Authentication fails?
│   ├─▶ For basic: verify username/password
│   ├─▶ For robot: check format robot$project+name
│   └─▶ Test: curl -u "user:pass" Harbor API
│
├─▶ No entities synced?
│   ├─▶ Check projects exist in Harbor
│   ├─▶ Review filters (might be too restrictive)
│   └─▶ Run with logLevel: DEBUG
│
├─▶ Webhooks not working?
│   ├─▶ Verify webhook secret matches
│   ├─▶ Check endpoint is publicly accessible
│   └─▶ Use Harbor's "Test Endpoint" button
│
└─▶ Integration crashes?
    ├─▶ Check logs for stack traces
    ├─▶ Verify .venv dependencies are installed
    └─▶ Run: make test to verify installation
```

## Performance Tuning Guide

### Small Harbor Instance (< 100 artifacts)
```yaml
maxConcurrentRequests: 3
maxRetries: 3
retryJitterSeconds: 0.5
```

### Medium Harbor Instance (100-1000 artifacts)
```yaml
maxConcurrentRequests: 5  # Default
maxRetries: 5
retryJitterSeconds: 0.5
```

### Large Harbor Instance (> 1000 artifacts)
```yaml
maxConcurrentRequests: 10
maxRetries: 5
retryJitterSeconds: 1.0

# Use aggressive filtering
projects: ["prod-only"]
artifactVulnSeverityAtLeast: "High"
```

### Rate-Limited Environment
```yaml
maxConcurrentRequests: 2
maxRetries: 10
retryJitterSeconds: 2.0

# Respect rate limits
timeout: 30
```

## File Checklist for Submission

```
Essential Files (Must Have)
✓ README.md                    - Main documentation
✓ SUBMISSION.md                - Submission package info
✓ SETUP_GUIDE.md              - This file
✓ CHANGELOG.md                 - Version history
✓ quick-start.sh              - Automated setup
✓ main.py                      - Entry point
✓ integration.py               - Configuration
✓ client.py                    - HTTP client

Source Code (Core)
✓ exporters/*.py              - Data fetchers
✓ mappers/*.py                - Entity mappers
✓ webhooks/handler.py         - Webhook processor
✓ logging_utils/structured.py - Logging
✓ models/*.py                  - Type definitions

Configuration (Examples)
✓ examples/config.sample.yaml  - Sample config
✓ examples/mappings.yaml       - Port mappings
✓ examples/blueprints/*.yaml   - 4 blueprints

Tests (Verification)
✓ tests/test_*.py              - 10 test files
✓ tests/conftest.py            - Test fixtures

Build Files
✓ pyproject.toml               - Dependencies
✓ Makefile                     - Build commands
✓ .port/spec.yaml             - Port spec
```

## Next Steps After Setup

1. **Verify Data Quality**
   ```bash
   # Check entity counts
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.getport.io/v1/blueprints/harborProject/entities
   ```

2. **Create Dashboards**
   - Vulnerability overview
   - Repository usage
   - Project health

3. **Set Up Alerts**
   - Critical CVEs detected
   - New high-severity vulnerabilities
   - Failed scans

4. **Integrate with CI/CD**
   - Trigger resync on deployments
   - Update artifact metadata
   - Track image lineage

5. **Monitor Performance**
   ```bash
   # Watch logs
   tail -f harbor-integration.log | grep "harbor.resync.summary"

   # Check Port API usage
   # Review structured logs for latency
   ```

## Support Resources

- **Documentation:** [README.md](README.md)
- **Issues:** [GitHub Issues](https://github.com/port-labs/ocean/issues)
- **Port Docs:** https://docs.getport.io
- **Harbor Docs:** https://goharbor.io/docs/

---

**Last Updated:** October 15, 2025
**Integration Version:** 0.2.0
