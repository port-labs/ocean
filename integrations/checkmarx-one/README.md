# Checkmarx One Integration

A comprehensive integration that imports Checkmarx One security scanning data into Port, providing complete visibility into your application security posture.

## Overview

This integration synchronizes your Checkmarx One data with Port, creating a comprehensive view of your security landscape including:

- **Applications** - High-level business applications and their security posture
- **Projects** - Code repositories and their scan configurations  
- **Scans** - Security scans across multiple scan engines (SAST, SCA, KICS, Container Security, API Security, DAST)
- **Scan Results** - Detailed vulnerability findings with full context and metadata

## Features

### Multi-Scanner Support
- **SAST** (Static Application Security Testing) - Source code vulnerability detection
- **SCA** (Software Composition Analysis) - Open source dependency vulnerabilities
- **KICS** (Keeping Infrastructure as Code Secure) - Infrastructure as Code scanning
- **Container Security** - Container image vulnerability scanning
- **API Security** - API endpoint security analysis
- **DAST** (Dynamic Application Security Testing) - Runtime vulnerability detection

### Advanced Filtering
- Filter by severity levels (CRITICAL, HIGH, MEDIUM, LOW, INFO)
- Filter by vulnerability states (TO_VERIFY, CONFIRMED, URGENT, etc.)
- Filter by scan status (NEW, RECURRENT, FIXED)
- Filter by scanner types to focus on specific security domains
- Exclude development/test dependencies from SCA results

### Real-time Updates
- Live synchronization of scan results as they complete
- Automatic project discovery and updates
- Delta sync capabilities for efficient data updates

## Prerequisites

- Checkmarx One account with API access
- Valid API credentials (API Key or OAuth Client)
- Network connectivity to your Checkmarx One instance

## Setup

### Authentication Options

#### Option 1: API Key Authentication
1. Navigate to your Checkmarx One console
2. Go to Settings → API Keys
3. Generate a new API key with appropriate permissions
4. Configure the integration with:
   - `CHECKMARX_BASE_URL`: Your Checkmarx One instance URL
   - `CHECKMARX_API_KEY`: Your generated API key

#### Option 2: OAuth Client Authentication  
1. Navigate to your Checkmarx One console
2. Go to Settings → OAuth Clients
3. Create a new OAuth client
4. Configure the integration with:
   - `CHECKMARX_BASE_URL`: Your Checkmarx One instance URL
   - `CHECKMARX_CLIENT_ID`: Your OAuth client ID
   - `CHECKMARX_CLIENT_SECRET`: Your OAuth client secret

### Required Permissions

Ensure your API credentials have the following permissions:
- `scan-results.read` - Read scan results
- `scans.read` - Read scan information
- `projects.read` - Read project information  
- `applications.read` - Read application information

## Configuration

### Basic Configuration

```yaml
resources:
  - kind: application
    selector:
      query: 'true'
      
  - kind: project
    selector:
      query: 'true'
      
  - kind: scan
    selector:
      query: 'true'
      projectIds: [] # Optional: filter by specific project IDs
      
  - kind: scan_result
    selector:
      query: 'true'
      severity: ["CRITICAL", "HIGH"] # Optional: filter by severity
      state: ["TO_VERIFY", "CONFIRMED"] # Optional: filter by state
      exclude_result_types: ["DEV_AND_TEST"] # Exclude dev/test dependencies
```

### Advanced Filtering Examples

#### Filter by Scanner Types
```yaml
resources:
  - kind: scan_result
    selector:
      query: 'true'
      scanner_types: ["sast", "sca"] # Only SAST and SCA results
      severity: ["CRITICAL", "HIGH"]
```

#### Application-Focused Configuration
```yaml
resources:
  - kind: application
    selector:
      query: 'true'
      criticality: [2, 3] # Only medium and high criticality apps
      
  - kind: project
    selector:
      query: 'true'
      applicationIds: ["app-123", "app-456"] # Projects from specific apps
```

#### Production-Only Scans
```yaml
resources:
  - kind: scan
    selector:
      query: 'true'
      scan_status: ["Completed"] # Only completed scans
      scanner_types: ["sast", "sca", "kics"] # Exclude DAST for prod
```

## Use Cases

### Development Teams
- **Vulnerability Tracking**: Track security issues across all projects
- **Technical Debt**: Monitor accumulation of security findings
- **Code Quality Gates**: Enforce security standards before releases
- **Dependency Management**: Track vulnerable open source components

### Security Teams  
- **Security Posture**: Enterprise-wide view of security health
- **Risk Assessment**: Prioritize remediation based on severity and business impact
- **Compliance**: Track security scanning coverage across applications
- **Trend Analysis**: Monitor security improvements over time

### Platform Teams
- **Scanning Coverage**: Ensure all projects have active security scanning
- **Scanner Adoption**: Track usage of different scanning engines
- **Infrastructure Security**: Monitor KICS and Container Security findings
- **API Security**: Track API endpoint vulnerabilities

### DevSecOps
- **Shift-Left Integration**: Embed security in development workflows  
- **Automated Remediation**: Trigger fixes based on vulnerability data
- **Security Metrics**: Track MTTR for security issue resolution
- **Pipeline Integration**: Security gates in CI/CD pipelines

## Data Model

### Applications
Represent business applications containing multiple projects:
- Basic metadata (name, description, criticality)
- Business context (tags, rules)
- Associated projects relationship

### Projects  
Represent code repositories or scanning targets:
- Repository information (URL, branch, origin)
- Associated applications
- Scan configuration and history
- Project grouping and tagging

### Scans
Represent individual security scanning operations:
- Scan status and timing information
- Scanner engines used (SAST, SCA, KICS, etc.)
- Source information (Git, upload)
- Associated project relationship

### Scan Results
Represent individual vulnerability findings:
- Vulnerability details (severity, CWE, CVE)
- Scanner-specific metadata
- File/line location (for SAST)
- Package information (for SCA)
- State tracking (verified, false positive, etc.)

## Port Entities

The integration creates the following Port entities:

1. **checkmarxApplication** - Business applications
2. **checkmarxProject** - Code projects/repositories  
3. **checkmarxScan** - Security scans
4. **checkmarxScanResult** - Individual vulnerability findings

Each entity includes relevant properties, relations, and aggregation properties for comprehensive security analytics.

## Monitoring and Troubleshooting

### Health Checks
The integration provides built-in health monitoring:
- API connectivity validation
- Authentication verification
- Rate limit monitoring
- Sync status tracking

### Common Issues

**Authentication Failures**
- Verify API credentials are correct
- Check credential permissions in Checkmarx One
- Ensure network connectivity to Checkmarx instance

**Missing Data**
- Verify scanner permissions are enabled
- Check project visibility settings
- Confirm scan completion status

**Performance Issues**
- Adjust page sizes for large datasets
- Enable result filtering to reduce data volume
- Monitor rate limit compliance

### Logging
Enable debug logging to troubleshoot issues:
```yaml
LOG_LEVEL: DEBUG
```

## Support

For integration support:
- Check [Ocean documentation](https://ocean.getport.io/)
- Review [Port documentation](https://docs.port.io/)  
- Contact Port support for technical assistance

## Contributing

To contribute improvements:
1. Follow [Ocean integration development guidelines](https://ocean.getport.io/develop-an-integration/)
2. Submit pull requests with comprehensive testing
3. Include documentation updates for new features