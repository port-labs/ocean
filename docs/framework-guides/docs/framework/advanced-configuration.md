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

## Ocean SSL verification settings

Ocean exposes structured TLS settings for **Port API** traffic and **third-party API** traffic (Jira, GitLab, GitHub, etc.). These are separate from `SSL_CERT_FILE` / `SSL_CERT_DIR`: use Ocean settings when the CA is trusted but Python 3.13+ rejects the certificate for strict X.509 rules (for example missing Authority Key Identifier behind an SSL inspection proxy).

Settings are read from environment variables at startup (Pydantic nested `OCEAN__` convention). If unset, defaults are secure: certificate and hostname validation on, strict X.509 profile on.

### Environment variables

| Variable | Default | Applies to |
|----------|---------|------------|
| `OCEAN__SSL__PORT__VERIFY` | `true` | Port API (`api.getport.io`, ingest, etc.) |
| `OCEAN__SSL__PORT__X509__STRICT` | `true` | Port API |
| `OCEAN__SSL__THIRD_PARTY__VERIFY` | `true` | Third-party APIs (GitLab, Jira, Datadog, …) |
| `OCEAN__SSL__THIRD_PARTY__X509__STRICT` | `true` | Third-party APIs |

### What each setting does

| `verify` | `x509.strict` | Behavior |
|----------|---------------|----------|
| `true` | `true` | Default — same as stock httpx / Python TLS |
| `true` | `false` | Still validates certificate chain and hostname; relaxes Python 3.13+ `VERIFY_X509_STRICT` (common fix for corporate SSL inspection / AKI-less proxy certs) |
| `false` | (ignored) | Disables all TLS verification — **break-glass only** |

### Corporate proxy / SSL inspection (Python 3.13+)

If TLS to a third-party API fails after upgrading to Python 3.13, and traffic goes through a corporate firewall that re-signs certificates, try:

```bash showLineNumbers
OCEAN__SSL__THIRD_PARTY__X509__STRICT=false
```

Only change Port API settings if Port calls also fail:

```bash showLineNumbers
OCEAN__SSL__PORT__X509__STRICT=false
```

If the private CA is not in the system trust store, configure `SSL_CERT_FILE` or `SSL_CERT_DIR` **first**. Ocean SSL settings do not replace trusting your internal CA.

### Which integrations are covered

`OCEAN__SSL__THIRD_PARTY__*` applies to integrations that use Ocean's `http_async_client` or `OceanAsyncClient` without passing an explicit `verify=` argument — **38 integrations**, including gitlab-v2, github, jira, azure-devops, and snyk.

Not covered: vendor SDK integrations (aws, azure, gcp, kafka, gitlab v1, newrelic), the **custom** integration (uses its own `verify_ssl` config), and **argocd** when `allow_insecure=true`.

### Security notes

- Prefer `x509.strict=false` over `verify=false`. Non-strict X.509 still validates the chain and hostname; `verify=false` disables all protection.
- Ocean logs a warning at startup when any non-default SSL setting is active.
- Do not use `verify=false` in production without explicit security approval.
