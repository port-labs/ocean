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
