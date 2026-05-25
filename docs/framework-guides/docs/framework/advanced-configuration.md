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

Ocean can configure SSL certificate verification separately for Port-owned requests and third-party integration requests.

Port SSL settings apply to Ocean's internal Port clients, including requests to Port's API and Port lifecycle services. Third-party SSL settings apply to Ocean's shared third-party HTTP client (`http_async_client`) and to `OceanAsyncClient` instances that do not explicitly pass a `verify` value.

These settings do not automatically affect integrations that create their own raw `httpx.AsyncClient` instances.

### Port API and lifecycle requests

- `OCEAN__PORT_VERIFY_SSL`: Enables or disables SSL certificate verification for Port-owned requests.
  - Default: `true`
  - Set to `false` to pass `verify=False` to HTTPX.
  - When this is `false`, `OCEAN__PORT_DISABLE_STRICT_SSL_VERIFICATION` is ignored because certificate verification is disabled completely.

- `OCEAN__PORT_DISABLE_STRICT_SSL_VERIFICATION`: Disables only Python's strict X.509 verification flag for Port-owned requests.
  - Default: `false`
  - Set to `true` to keep certificate verification enabled while removing `ssl.VERIFY_X509_STRICT` from the SSL context.

### Third-party integration requests

- `OCEAN__THIRD_PARTY_VERIFY_SSL`: Enables or disables SSL certificate verification for Ocean-managed third-party requests.
  - Default: `true`
  - Set to `false` to pass `verify=False` to HTTPX.
  - When this is `false`, `OCEAN__THIRD_PARTY_DISABLE_STRICT_SSL_VERIFICATION` is ignored because certificate verification is disabled completely.

- `OCEAN__THIRD_PARTY_DISABLE_STRICT_SSL_VERIFICATION`: Disables only Python's strict X.509 verification flag for Ocean-managed third-party requests.
  - Default: `false`
  - Set to `true` to keep certificate verification enabled while removing `ssl.VERIFY_X509_STRICT` from the SSL context.

### Strict verification mode

When one of the `*_DISABLE_STRICT_SSL_VERIFICATION` settings is `true`, Ocean creates a custom SSL context and passes it to HTTPX. The context keeps HTTPX's usual certificate authority lookup order:

1. `SSL_CERT_FILE`, if set
2. `SSL_CERT_DIR`, if set
3. HTTPX's default `certifi` CA bundle

Ocean then removes only the `ssl.VERIFY_X509_STRICT` flag from that context. Use this mode when certificate validation should remain enabled, but Python's strict X.509 checks are too strict for a certificate chain you already trust.

### Usage examples

```bash showLineNumbers
# Keep Port certificate verification enabled, but disable strict X.509 checks.
export OCEAN__PORT_DISABLE_STRICT_SSL_VERIFICATION=true

# Disable Port certificate verification completely. Not recommended for production.
export OCEAN__PORT_VERIFY_SSL=false

# Keep third-party certificate verification enabled, but disable strict X.509 checks.
export OCEAN__THIRD_PARTY_DISABLE_STRICT_SSL_VERIFICATION=true

# Disable third-party certificate verification completely. Not recommended for production.
export OCEAN__THIRD_PARTY_VERIFY_SSL=false
```

### Security considerations

- Prefer `*_DISABLE_STRICT_SSL_VERIFICATION=true` over `*_VERIFY_SSL=false` when you only need to work around strict X.509 validation.
- Use `*_VERIFY_SSL=false` only for local development, testing, or controlled troubleshooting. It disables certificate verification completely and makes requests vulnerable to man-in-the-middle attacks.
- If you need custom trusted certificate authorities, configure `SSL_CERT_FILE` or `SSL_CERT_DIR` instead of disabling verification.
