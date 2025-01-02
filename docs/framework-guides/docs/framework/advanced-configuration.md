---
title: Advanced Configuration
sidebar_label: ⚙️ Advanced Configuration
sidebar_position: 3
---

# ⚙️ Advanced Configuration

The Ocean framework provides extensive configuration capabilities through environment variables, YAML files, and configuration providers. This flexibility allows you to customize how Ocean operates in different environments.

## Overview

The framework supports several configuration methods:
- Environment variables with the `OCEAN__` prefix
- YAML configuration files (`config.yaml`)
- Environment files (`.env`)
- Configuration providers for value interpolation
- Sensitive field handling

These configurations enable Ocean to work seamlessly in various enterprise environments while maintaining security and flexibility.

## Environment Variable Configuration

### Environment Variable Prefix

Ocean uses the `OCEAN__` prefix for all its environment variables. For nested configurations, use double underscores (`__`) as delimiters.

Example:
```bash showLineNumbers
OCEAN__INTEGRATION__IDENTIFIER=my-integration
OCEAN__INTEGRATION__TYPE=jira
OCEAN__CONFIG__API_TOKEN=secret-token
```

### Environment File Configuration (Recommended)

Ocean uses `.env` files as the primary and recommended method for configuration. The framework automatically loads environment variables from a `.env` file in your project directory, providing a secure and convenient way to manage configuration:

```bash showLineNumbers
# .env file - Primary configuration method
OCEAN__LOG_LEVEL=DEBUG
OCEAN__INTEGRATION__IDENTIFIER=my-integration
OCEAN__PORT__CLIENT_ID=your-client-id
OCEAN__PORT__CLIENT_SECRET=your-client-secret
OCEAN__CONFIG__API_TOKEN=your-api-token

# Integration-specific configuration
OCEAN__CONFIG__BASE_URL=https://your-instance.atlassian.net
OCEAN__CONFIG__USERNAME=your-username
```

Benefits of using .env files:
- Secure storage of sensitive information
- Easy environment-specific configuration
- Prevents accidental commits of secrets
- Supports development and production environments
- Automatic loading by the Ocean framework

## Configuration Providers

Ocean supports value interpolation using configuration providers. This allows you to reference environment variables in your YAML configuration:

```yaml showLineNumbers
integration:
  identifier: "{{ from env INTEGRATION_ID }}"
  type: "jira"
config:
  apiToken: "{{ from env JIRA_API_TOKEN }}"
```

The `from env` provider loads values from environment variables, making it easy to keep sensitive information out of your configuration files.

## Common Environment Variables

Ocean provides several built-in environment variables to control its behavior:

### Core Variables

- `OCEAN__LOG_LEVEL`: Controls logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `OCEAN__INTEGRATION__IDENTIFIER`: Unique identifier for your integration
- `OCEAN__INTEGRATION__TYPE`: Type of integration (e.g., jira, gitlab)
- `OCEAN__PORT__CLIENT_ID`: Port platform client ID
- `OCEAN__PORT__CLIENT_SECRET`: Port platform client secret
- `OCEAN__PORT__BASE_URL`: Port API base URL

Example:
```bash showLineNumbers
OCEAN__LOG_LEVEL=DEBUG
OCEAN__INTEGRATION__IDENTIFIER=my-jira-integration
OCEAN__PORT__BASE_URL=https://api.getport.io
```

### Integration-Specific Configuration

Each integration type can define its own configuration variables. Here's an example for the Jira integration:

```yaml showLineNumbers
# config.yaml
integration:
  identifier: "{{ from env INTEGRATION_ID }}"
  type: "jira"

config:
  # Jira-specific configuration
  baseUrl: "{{ from env JIRA_URL }}"
  username: "{{ from env JIRA_USERNAME }}"
  apiToken: "{{ from env JIRA_API_TOKEN }}"

  # Optional configurations
  projectKeys: ["PROJ1", "PROJ2"]
  maxResults: 100

  # Event listener configuration
  eventListener:
    type: "POLLING"
    config:
      interval: 300  # Polling interval in seconds
```

Environment variables for this configuration:
```bash showLineNumbers
OCEAN__CONFIG__BASE_URL=https://your-instance.atlassian.net
OCEAN__CONFIG__USERNAME=your-username
OCEAN__CONFIG__API_TOKEN=your-api-token
```

### Advanced Integration Settings

Additional settings that can be configured:

- `OCEAN__CONFIG__MAX_RETRIES`: Maximum number of API retry attempts
- `OCEAN__CONFIG__TIMEOUT`: API request timeout in seconds
- `OCEAN__CONFIG__BATCH_SIZE`: Number of items to process in each batch
- `OCEAN__EVENT_LISTENER__TYPE`: Event listener type (POLLING, KAFKA, WEBHOOK)

These settings can be configured either through environment variables or in the `config.yaml` file.

## Proxy configuration

### Proxy Environment Variables

#### `HTTP_PROXY`, `HTTPS_PROXY` & `ALL_PROXY`
These environment variables configure proxy servers for different types of requests:
- `HTTP_PROXY`: Handles HTTP requests
- `HTTPS_PROXY`: Handles HTTPS requests
- `ALL_PROXY`: Handles all types of requests

Each variable should be set to the URL of the corresponding proxy server.

For example:
```bash showLineNumbers
HTTP_PROXY=http://my-proxy.com:1111
HTTPS_PROXY=http://my-proxy.com:2222
ALL_PROXY=http://my-proxy.com:3333
```

#### `NO_PROXY`
This environment variable allows you to bypass the proxy for specific addresses:
- Accepts a comma-separated list of hostnames or URLs
- Useful for accessing internal services directly
- Common for local development environments

For example:
```bash showLineNumbers
NO_PROXY=http://127.0.0.1,google.com
```

For more information take a look at the HTTPX [proxy configuration documentation](https://www.python-httpx.org/environment_variables/#proxies).

## SSL/TLS Configuration

The Ocean framework provides comprehensive SSL/TLS configuration options through environment variables. These settings allow you to customize how the framework handles secure connections, certificates, and encryption.

### SSL Environment Variables

#### `SSLKEYLOGFILE`
This variable enables SSL/TLS debugging capabilities:
- Specifies where to log SSL/TLS key information
- Enables network analysis tools like Wireshark to inspect encrypted traffic
- Useful for troubleshooting SSL/TLS connection issues

Example:
```bash showLineNumbers
SSLKEYLOGFILE=/path/to/sslkeylogfile.txt
```

#### `SSL_CERT_DIR`
This variable configures certificate directory settings:
- Points to a directory containing multiple certificate files
- Useful for managing multiple trusted CA certificates
- Common in enterprise environments with custom certificate authorities

Example:
```bash showLineNumbers
SSL_CERT_DIR=/etc/ssl/certs
```

#### `SSL_CERT_FILE`
This variable specifies a certificate bundle file:
- Points to a single file containing multiple CA certificates
- Certificates must be in PEM format
- Used when validating server certificates against specific CAs

Example:
```bash showLineNumbers
SSL_CERT_FILE=/path/to/cacert.pem
```

### Use Cases

These SSL/TLS configurations are particularly useful in:
- Enterprise environments with custom certificate authorities
- Development environments requiring SSL/TLS debugging
- Environments with specific security requirements
- Scenarios involving self-signed certificates

For detailed information about SSL configuration options, refer to the HTTPX [SSL configuration documentation](https://www.python-httpx.org/environment_variables/#sslkeylogfile).

## Sensitive Field Handling

Ocean provides built-in support for handling sensitive information through the `sensitive` field attribute. Fields marked as sensitive are automatically handled with extra care:

```python showLineNumbers
from pydantic import BaseModel
from port_ocean import BaseOceanModel

class IntegrationConfig(BaseOceanModel):
    api_token: str = Field(..., sensitive=True)
    base_url: str

```

Sensitive fields are:
- Masked in logs and error messages
- Protected from accidental exposure
- Handled securely during serialization

This ensures that sensitive information like API tokens and credentials remains secure throughout the integration's lifecycle.
