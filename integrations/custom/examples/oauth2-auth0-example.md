# OAuth2 Configuration Example: Auth0 Management API

## Real-World Example: Auth0 Management API

Auth0 Management API uses OAuth2 Client Credentials flow to authenticate server-to-server requests.

### 1. Auth0 API Details

- **Base URL**: `https://YOUR_DOMAIN.auth0.com`
- **Token Endpoint**: `https://YOUR_DOMAIN.auth0.com/oauth/token`
- **API Endpoint**: `https://YOUR_DOMAIN.auth0.com/api/v2/users`
- **Grant Type**: `client_credentials`
- **Token Response**: `{"access_token": "...", "token_type": "Bearer", "expires_in": 86400}`

### 2. Ocean Custom Integration Configuration

#### Installation Config (Helm values.yaml or env vars)

```yaml
# Helm values.yaml
integration:
  config:
    baseUrl: "https://your-tenant.auth0.com"
    authType: "oauth2"
    authEndpoint: "https://your-tenant.auth0.com/oauth/token"
    clientId: "${AUTH0_CLIENT_ID}"  # Or direct value
    clientSecret: "${AUTH0_CLIENT_SECRET}"  # Or direct value
    grantType: "client_credentials"  # Optional, this is the default
    tokenPath: "access_token"  # Optional, this is the default
```

#### Environment Variables (Alternative)

```bash
export OCEAN__INTEGRATION__CONFIG__BASE_URL="https://your-tenant.auth0.com"
export OCEAN__INTEGRATION__CONFIG__AUTH_TYPE="oauth2"
export OCEAN__INTEGRATION__CONFIG__AUTH_ENDPOINT="https://your-tenant.auth0.com/oauth/token"
export OCEAN__INTEGRATION__CONFIG__CLIENT_ID="your-client-id"
export OCEAN__INTEGRATION__CONFIG__CLIENT_SECRET="your-client-secret"
```

### 3. How It Works

**Step 1: First API Request**
```
1. Integration makes request to /api/v2/users
2. No token cached yet → calls auth_handler.get_token()
3. POST to https://your-tenant.auth0.com/oauth/token
   Body: grant_type=client_credentials&client_id=...&client_secret=...
4. Receives: {"access_token": "eyJ...", "expires_in": 86400}
5. Extracts token from "access_token" field
6. Caches token
7. Retries original request with Authorization: Bearer eyJ...
```

**Step 2: Subsequent Requests**
```
1. Integration makes request to /api/v2/users
2. Token cached → uses cached token
3. Request succeeds ✅
```

**Step 3: Token Expired (401 Error)**
```
1. Integration makes request to /api/v2/users
2. API returns 401 Unauthorized
3. Integration calls auth_handler.refresh_token()
4. Fetches new token from auth endpoint
5. Retries request with new token
6. Request succeeds ✅
```

### 4. Mapping Example

```yaml
# Mapping to sync Auth0 users to Port
resources:
  - kind: user
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .user_id
          title: .name
          blueprint: '"auth0User"'
          properties:
            email: .email
            createdAt: .created_at
            lastLogin: .last_login
    endpoint:
      path: "/api/v2/users"
      method: GET
      # Token is automatically added to Authorization header
      # No need to specify auth in mapping!
```

### 5. What Gets Sent

**Token Request (automatic, behind the scenes):**
```http
POST https://your-tenant.auth0.com/oauth/token HTTP/1.1
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET
```

**API Request (with cached token):**
```http
GET https://your-tenant.auth0.com/api/v2/users HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 6. Common Variations

#### Different Token Path
Some APIs return tokens in nested objects:
```json
{
  "data": {
    "token": "eyJ...",
    "expires_in": 3600
  }
}
```

**Configuration:**
```yaml
tokenPath: "data.token"  # Dot notation to extract nested token
```

#### Different Grant Type
Some APIs use `password` grant type:
```yaml
grantType: "password"
# Would need additional fields like username/password
# (Not currently supported, but could be added)
```

### 7. Error Handling

**Wrong Credentials (on first request):**
```
❌ OAuth2 authentication failed with 401.
Please check your credentials (client_id, client_secret).
Response: {"error":"invalid_client","error_description":"..."}
```
→ **No retry loop** - fails immediately with clear error

**Token Expired (during sync):**
```
ℹ️ Received 401 Unauthorized, refreshing OAuth2 token and retrying...
✅ OAuth2 token acquired successfully
✅ Request succeeded after refresh
```

### 8. Comparison with Other Auth Types

| Auth Type | Config Fields | Use Case |
|-----------|--------------|----------|
| `bearer_token` | `apiToken` | Static tokens that don't expire |
| `oauth2` | `clientId`, `clientSecret`, `authEndpoint` | Dynamic tokens that expire and refresh |
| `basic` | `username`, `password` | Basic HTTP auth |
| `api_key` | `apiKey`, `apiKeyHeader` | API key in header |

**When to use OAuth2:**
- ✅ Tokens expire and need refreshing
- ✅ Server-to-server authentication (client credentials)
- ✅ APIs that require OAuth2 compliance
- ✅ Tokens are too long-lived to store statically

**When NOT to use OAuth2:**
- ❌ Static API keys that never expire
- ❌ Simple bearer tokens you can store directly
- ❌ APIs that don't support OAuth2

