# Checkmarx One

An integration used to import Checkmarx One resources into Port.

## Configuration

This integration uses API key authentication for Checkmarx One. You'll need to configure the following environment variables:

### Required Environment Variables

- `OCEAN__INTEGRATION__CONFIG__CHECKMARX_BASE_URL`: Your Checkmarx One base URL (e.g., https://ast.checkmarx.net)
- `OCEAN__INTEGRATION__CONFIG__CHECKMARX_IAM_URL`: Your Checkmarx One IAM URL (e.g., https://iam.checkmarx.net)
- `OCEAN__INTEGRATION__CONFIG__CHECKMARX_TENANT`: Your Checkmarx One tenant name
- `OCEAN__INTEGRATION__CONFIG__CHECKMARX_API_KEY`: Your Checkmarx One API key
- `OCEAN__PORT__CLIENT_ID`: Your Port OAuth client ID
- `OCEAN__PORT__CLIENT_SECRET`: Your Port OAuth client secret
- `OCEAN__BASE_URL`: The base URL of your Ocean instance (required for webhook processing)

### Optional Environment Variables

- `OCEAN__INTEGRATION__CONFIG__WEBHOOK_SECRET`: Secret used to sign and validate incoming webhooks from Checkmarx One

### Example .env file

```bash
OCEAN__PORT__CLIENT_ID=<port_client_id>
OCEAN__PORT__CLIENT_SECRET=<port_client_secret>
OCEAN__INTEGRATION__CONFIG__CHECKMARX_BASE_URL=https://ast.checkmarx.net
OCEAN__INTEGRATION__CONFIG__CHECKMARX_IAM_URL=https://iam.checkmarx.net
OCEAN__INTEGRATION__CONFIG__CHECKMARX_TENANT=<your_tenant>
OCEAN__INTEGRATION__CONFIG__CHECKMARX_API_KEY=<your_api_key>
OCEAN__INTEGRATION__CONFIG__WEBHOOK_SECRET=<webhook_secret>
OCEAN__BASE_URL=<your_ocean_base_url>
```

## Resources

This integration provides the following resources:

- **project**: Checkmarx One projects with scanning capabilities
- **scan**: Security scans performed on projects
- **scan_result**: Security vulnerabilities and issues found in scans

## Authentication

The integration automatically handles OAuth2 token generation and renewal using your API key. Tokens are cached and refreshed as needed.

## Webhooks

Webhooks must be manually registered in your Checkmarx One dashboard. The integration will process the following webhook events:

- Project creation events
- Scan completion events
- Scan result updates

If a webhook secret is configured, make sure to set the same webhook secret used during registration in the .env file via `OCEAN__INTEGRATION__CONFIG__WEBHOOK_SECRET`.

**Important**: The `OCEAN__BASE_URL` environment variable is required for webhook processing to work. Without it, you'll see the warning "No base URL provided, skipping webhook processing" and webhooks will not be processed.

## Configuration Options

### Scan Result Filtering

You can configure scan result filtering using the following options in your resource configuration:

- **severity**: Filter by severity level (CRITICAL, HIGH, MEDIUM, LOW, INFO)
- **state**: Filter by state (TO_VERIFY, CONFIRMED, URGENT, NOT_EXPLOITABLE, PROPOSED_NOT_EXPLOITABLE, FALSE_POSITIVE)
- **status**: Filter by status (NEW, RECURRENT, FIXED)
- **exclude_result_types**: Exclude result types (DEV_AND_TEST, NONE)

### Scan Filtering

You can limit scans to specific projects using the `projectIds` selector in your scan resource configuration.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/code-quality-security/checkmarx-one)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)
