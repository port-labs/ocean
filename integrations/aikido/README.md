# Aikido

An integration used to import Aikido resources into Port.

## Configuration

This integration uses OAuth2 client credentials for authentication. You'll need to configure the following environment variables:

### Required Environment Variables

- `OCEAN__INTEGRATION__CONFIG__AIKIDO_CLIENT_ID`: Your Aikido OAuth client ID
- `OCEAN__INTEGRATION__CONFIG__AIKIDO_CLIENT_SECRET`: Your Aikido OAuth client secret
- `OCEAN__PORT__CLIENT_ID`: Your Port OAuth client ID
- `OCEAN__PORT__CLIENT_SECRET`: Your Port OAuth client secret
- `OCEAN__BASE_URL`: The base URL of your Ocean instance

### Optional Environment Variables

- `OCEAN__INTEGRATION__CONFIG__AIKIDO_API_URL`: Custom Aikido API URL (defaults to `https://app.aikido.dev`)

- `OCEAN__INTEGRATION__CONFIG__WEBHOOK_SECRET`: Secret used to sign and validate incoming webhooks from Aikido

### Example .env file

```bash
OCEAN__PORT__CLIENT_ID=<port_client_id>
OCEAN__PORT__CLIENT_SECRET=<port_client_secret>
OCEAN__INTEGRATION__CONFIG__AIKIDO_CLIENT_SECRET=<aikido_client_secret>
OCEAN__INTEGRATION__CONFIG__AIKIDO_CLIENT_ID=<aikido_client_id>
OCEAN__INTEGRATION__CONFIG__AIKIDO_API_URL=https://app.aikido.dev
OCEAN__INTEGRATION__CONFIG__WEBHOOK_SECRET=<webhook_secret>
OCEAN__BASE_URL=<base_url>

```

## Resources

This integration provides the following resources:

- **repositories**: Aikido repositories with code scanning capabilities
- **issues**: Security issues and vulnerabilities found in repositories

## Authentication

The integration automatically handles OAuth2 token generation and renewal using your client credentials. Tokens are cached and refreshed as needed.

## Webhooks

Webhooks must be manually registered in your Aikido dashboard:
https://app.aikido.dev/settings/integrations/api/webhooks

If Webhook secret is used, make sure to set the same webhook secret used during registration in the .env file via `OCEAN__INTEGRATION__CONFIG__WEBHOOK_SECRET`

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/code-quality-security/aikido)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)
