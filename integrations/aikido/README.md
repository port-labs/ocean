# Aikido

An integration used to import Aikido resources into Port.

## Configuration

This integration uses OAuth2 client credentials for authentication. You'll need to configure the following environment variables:

### Required Environment Variables

- `AIKIDO_CLIENT_ID`: Your Aikido OAuth client ID
- `AIKIDO_CLIENT_SECRET`: Your Aikido OAuth client secret
- `AIKIDO_WEBHOOK_SECRET`: Secret used to sign and validate incoming webhooks from Aikido

### Optional Environment Variables

- `AIKIDO_API_URL`: Custom API URL (defaults to `https://app.aikido.dev/api/public/v1`)

### Example .env file

```bash
# Aikido OAuth2 Configuration
AIKIDO_CLIENT_ID=your_aikido_client_id_here
AIKIDO_CLIENT_SECRET=your_aikido_client_secret_here
AIKIDO_WEBHOOK_SECRET=your_webhook_secret_here
AIKIDO_API_URL=https://app.aikido.dev/api/public/v1
```

## Resources

This integration provides the following resources:

- **repositories**: Aikido repositories with code scanning capabilities
- **issues**: Security issues and vulnerabilities found in repositories

## Authentication

The integration automatically handles OAuth2 token generation and renewal using your client credentials. Tokens are cached and refreshed as needed.

## Webhooks

On startup, the integration will check if a webhook exists in Aikido for your Ocean instance. If not, it will create one using the provided webhook secret. Incoming webhook requests will be validated using this secret.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/code-quality-security/aikido)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)
