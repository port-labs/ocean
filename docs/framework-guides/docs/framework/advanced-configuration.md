---
title: Advanced Configuration
sidebar_label: ⚙️ Advanced Configuration
sidebar_position: 3
---

# ⚙️ Advanced configuration
The Ocean framework is based on a Python HTTP client called [HTTPX](https://www.python-httpx.org/). The HTTPX client provides out-of-the-box configuration capabilites, which allows configuring the client to work with:

- Self-signed certificates.
- Proxies.

These configurations are passed to the client using environment varaibles.

## Proxy configuration

### `HTTP_PROXY`, `HTTPS_PROXY` & `ALL_PROXY`
`HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` are environment variables used to specify a proxy server for handling HTTP, HTTPS, or all types of requests, respectively. The values assigned to these settings should be the URL of the proxy server.

For example:
```bash showLineNumbers
HTTP_PROXY=http://my-proxy.com:1111
HTTPS_PROXY=http://my-proxy.com:2222
ALL_PROXY=http://my-proxy.com:3333
```

### `NO_PROXY`

`NO_PROXY` allows blacklisting certain addresses from being handled through a proxy. This vairable accepts a comma-seperated list of hostnames or urls.

For example:
```bash showLineNumbers
NO_PROXY=http://127.0.0.1,google.com
```

For more information take a look at the HTTPX [proxy configuration documentation](https://www.python-httpx.org/environment_variables/#proxies).

## SSL Environment Configuration

`SSLKEYLOGFILE`, `SSL_CERT_DIR`, and `SSL_CERT_FILE` are environment variables that control various aspects of SSL (Secure Sockets Layer) communication.

### `SSLKEYLOGFILE`
This variable specifies the file path where SSL/TLS key information will be logged. This is particularly useful for debugging encrypted SSL/TLS connections, as it allows network analyzers like Wireshark to decrypt and inspect the traffic.

For example:
```bash showLineNumbers
SSLKEYLOGFILE=/path/to/sslkeylogfile.txt
```

### `SSL_CERT_DIR`
This variable sets the directory path where the program looks for SSL/TLS certificates. Instead of a single file, `SSL_CERT_DIR` points to a directory that contains multiple certificate files. This is useful when you have a collection of trusted CA (Certificate Authority) certificates split into different files.

For example:
```bash showLineNumbers
SSL_CERT_DIR=/etc/ssl/certs
```

### `SSL_CERT_FILE`
This variable points to a single file that contains a bundle of concatenated CA certificates, which are used to validate the SSL/TLS connections. The file should contain a series of trusted certificates in PEM format. This is useful when your application needs to validate server certificates against a specific set of CAs.

For example:
```bash showLineNumbers
SSL_CERT_FILE=/path/to/cacert.pem
```

These variables provide fine-grained control over SSL/TLS configurations in environments where default settings are not sufficient or need customization for specific requirements.

For more information take a look at the HTTPX [SSL configuration documentation](https://www.python-httpx.org/environment_variables/#sslkeylogfile).

## SSL certificate validation

Ocean framework provides flexibility in handling SSL certificate verification through environment variables. This is particularly useful when working with Python 3.13+ strict X.509 certificate verification or when you need to disable SSL verification for development or testing purposes.

The framework allows separate SSL configuration for Port API connections and third-party integration connections.

### Environment Variables

#### Port API Connections

The following environment variables configure SSL verification for connections to Port's API:

- `OCEAN__NO_STRICT_VERIFY_SSL`: Disable strict X.509 verification introduced in Python 3.13
  - Values: `false` (default) or `true`
  - Example: `OCEAN__NO_STRICT_VERIFY_SSL=true`
  - Use this if you encounter certificate validation issues with Port's API in Python 3.13

- `OCEAN__VERIFY_SSL`: Enable or disable SSL certificate verification completely
  - Values: `true` (default) or `false`
  - Example: `OCEAN__VERIFY_SSL=false`
  - Warning: Disabling this is not recommended for production use

#### Third-Party Integration Connections

These environment variables configure SSL verification for connections to third-party services:

- `OCEAN__THIRD_PARTY_NO_STRICT_VERIFY_SSL`: Disable strict X.509 verification for third-party connections
  - Values: `false` (default) or `true`
  - Example: `OCEAN__THIRD_PARTY_NO_STRICT_VERIFY_SSL=true`
  - Use this if you encounter certificate validation issues with third-party services in Python 3.13

- `OCEAN__THIRD_PARTY_VERIFY_SSL`: Enable or disable SSL verification for third-party connections
  - Values: `true` (default) or `false`
  - Example: `OCEAN__THIRD_PARTY_VERIFY_SSL=false`
  - Warning: Disabling this is not recommended for production use

### Usage Examples

#### Configure Port API SSL Verification

```bash
# Disable strict X.509 verification for Port API
export OCEAN__NO_STRICT_VERIFY_SSL=true

# Disable all SSL verification for Port API (Not Recommended)
export OCEAN__VERIFY_SSL=false
```

#### Configure Third-Party SSL Verification

```bash
# Disable strict X.509 verification for third-party services
export OCEAN__THIRD_PARTY_NO_STRICT_VERIFY_SSL=true

# Disable all SSL verification for third-party services (Not Recommended)
export OCEAN__THIRD_PARTY_VERIFY_SSL=false
```

### Security Considerations

- Disabling SSL verification (`*_VERIFY_SSL=false`) is not recommended for production environments as it makes your connections vulnerable to man-in-the-middle attacks.
- Disabling strict X.509 verification (`*_NO_STRICT_VERIFY_SSL=true`) should only be used when:
  1. You're encountering certificate validation issues due to the stricter verification
  2. You've verified that your certificates are otherwise valid and trusted
- Consider configuring SSL verification separately for Port API and third-party services based on your security requirements

### Troubleshooting

If you encounter SSL verification errors:

1. First, ensure your system's CA certificates are up to date
2. Identify whether the issue is with Port's API or third-party services
3. If using Python 3.13+ and encountering new certificate errors:
   - For Port API issues: Try setting `OCEAN__NO_STRICT_VERIFY_SSL=true`
   - For third-party service issues: Try setting `OCEAN__THIRD_PARTY_NO_STRICT_VERIFY_SSL=true`
4. For development/testing only, you can temporarily disable verification:
   - For Port API: Set `OCEAN__VERIFY_SSL=false`
   - For third-party services: Set `OCEAN__THIRD_PARTY_VERIFY_SSL=false`
5. Check the logs for any SSL-related warnings or errors