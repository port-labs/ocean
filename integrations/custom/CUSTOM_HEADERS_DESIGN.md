# Custom Headers Design Options

## Overview
This document outlines different approaches for loading custom HTTP headers into the Ocean Custom integration, considering requirements for Kubernetes, Docker, and GitHub Actions deployments.

## Requirements
- Support Kubernetes deployments (with secrets)
- Support Docker deployments
- Support GitHub Actions/CI/CD
- Follow Ocean's configuration conventions
- Simple, user-friendly approach
- No Helm chart code changes (preferred)

---

## Option 1: JSON Environment Variable (Current Implementation)

### How it works
- Config field: `customHeaders` (string, JSON format)
- User provides JSON string with header key-value pairs
- Supports environment variable references: `{"X-API-Key": "${CUSTOM_API_KEY}"}`
- Integration resolves `${VAR_NAME}` references to actual env var values

### Examples

**Kubernetes:**
```yaml
# User creates secret
apiVersion: v1
kind: Secret
metadata:
  name: custom-headers
stringData:
  X-Api-Key: "supersecretapikey"

# User injects as env var
env:
  - name: CUSTOM_API_KEY
    valueFrom:
      secretKeyRef:
        name: custom-headers
        key: X-Api-Key

# User sets JSON config
OCEAN__INTEGRATION__CONFIG__CUSTOM_HEADERS='{"X-API-Key": "${CUSTOM_API_KEY}"}'
```

**Docker:**
```bash
export CUSTOM_API_KEY="value"
export OCEAN__INTEGRATION__CONFIG__CUSTOM_HEADERS='{"X-API-Key": "${CUSTOM_API_KEY}"}'
```

**GitHub Actions:**
```yaml
env:
  CUSTOM_API_KEY: ${{ secrets.API_KEY }}
  OCEAN__INTEGRATION__CONFIG__CUSTOM_HEADERS: '{"X-API-Key": "${CUSTOM_API_KEY}"}'
```

### Pros
- ✅ Works everywhere (K8s, Docker, GitHub Actions)
- ✅ Already implemented
- ✅ Follows Ocean config convention
- ✅ No Helm chart changes needed

### Cons
- ❌ Two-step process (create secret/env vars + JSON config)
- ❌ Customer feedback: "confusing" and "two-step config approach"
- ❌ Requires JSON parsing and env var resolution

---

## Option 2: Secret Name → Environment Variables (Auto-prefix)

### How it works
- Config field: `customHeadersSecret` (string, secret name)
- Integration auto-generates prefix from secret name: `custom-headers` → `CUSTOM_HEADERS_`
- Reads all environment variables starting with that prefix
- Converts env var names to header names: `CUSTOM_HEADERS_X_API_KEY` → `X-Api-Key`

### Examples

**Kubernetes:**
```yaml
# User creates secret
apiVersion: v1
kind: Secret
metadata:
  name: custom-headers
stringData:
  X-Api-Key: "supersecretapikey"
  X-Tenant-Id: "tenant123"

# User configures envFrom (in values.yaml or pod spec)
envFrom:
  - secretRef:
      name: custom-headers
      prefix: CUSTOM_HEADERS_

# User sets config
OCEAN__INTEGRATION__CONFIG__CUSTOM_HEADERS_SECRET="custom-headers"
```

**Docker:**
```bash
export OCEAN__INTEGRATION__CONFIG__CUSTOM_HEADERS_SECRET="custom-headers"
export CUSTOM_HEADERS_X_API_KEY="value"
export CUSTOM_HEADERS_X_TENANT_ID="value"
```

**GitHub Actions:**
```yaml
env:
  OCEAN__INTEGRATION__CONFIG__CUSTOM_HEADERS_SECRET: custom-headers
  CUSTOM_HEADERS_X_API_KEY: ${{ secrets.API_KEY }}
  CUSTOM_HEADERS_X_TENANT_ID: ${{ secrets.TENANT_ID }}
```

### Implementation
```python
def _load_custom_headers(config):
    secret_name = config.get("custom_headers_secret")
    if not secret_name:
        return {}
    
    # Auto-generate prefix: "custom-headers" → "CUSTOM_HEADERS_"
    prefix = f"{secret_name.upper().replace('-', '_')}_"
    
    headers = {}
    for env_key, env_value in os.environ.items():
        if env_key.startswith(prefix):
            # CUSTOM_HEADERS_X_API_KEY → header: X-Api-Key
            header_name = env_key[len(prefix):].replace('_', '-')
            headers[header_name] = env_value
    
    return headers
```

### Pros
- ✅ Single config field (secret name)
- ✅ Works everywhere (same approach)
- ✅ K8s users: Use `envFrom` with prefix
- ✅ Docker/GitHub: Set env vars with prefix
- ✅ No Helm chart code changes (users configure `envFrom` themselves)

### Cons
- ❌ Requires users to configure `envFrom` manually in K8s (no automatic injection)
- ❌ Env var naming convention required (`CUSTOM_HEADERS_*`)

---

## Option 3: Secret Path (Volume Mount)

### How it works
- Config field: `customHeadersSecretPath` (string, file path)
- User mounts Kubernetes secret as volume
- Integration reads files from mounted path
- Each file = header name, file content = header value

### Examples

**Kubernetes:**
```yaml
# User creates secret
apiVersion: v1
kind: Secret
metadata:
  name: custom-headers
stringData:
  X-Api-Key: "supersecretapikey"
  X-Tenant-Id: "tenant123"

# User mounts secret as volume (in values.yaml or pod spec)
volumes:
  - name: custom-headers-volume
    secret:
      secretName: custom-headers
containers:
  - volumeMounts:
      - name: custom-headers-volume
        mountPath: /etc/custom-headers

# User sets config
OCEAN__INTEGRATION__CONFIG__CUSTOM_HEADERS_SECRET_PATH="/etc/custom-headers"
```

**Docker/GitHub Actions:**
- ❌ Not applicable (no volume mounts)

### Pros
- ✅ Single-step for K8s users (just mount secret)
- ✅ No Helm chart code changes (users configure volume mount)
- ✅ Kubernetes-native approach

### Cons
- ❌ Only works in Kubernetes
- ❌ Doesn't work for Docker/GitHub Actions
- ❌ Requires volume mount configuration

---

## Option 4: Hybrid - Secret Path + Env Vars (Priority-based)

### How it works
- Config fields: `customHeadersSecretPath` (optional) + `customHeadersPrefix` (optional)
- Priority 1: Try secret path (if configured and exists)
- Priority 2: Fall back to env vars with prefix
- Priority 3: Fall back to JSON env var (backward compatibility)

### Pros
- ✅ Flexible: supports both K8s volume mounts and env vars
- ✅ Works everywhere (with fallbacks)
- ✅ Backward compatible

### Cons
- ❌ More complex (multiple config fields)
- ❌ Multiple code paths
- ❌ User confusion: which method to use?

---

## Option 5: Configurable Prefix (Ocean Config Convention)

### How it works
- Config field: `customHeadersPrefix` (string, default: `CUSTOM_HEADER_`)
- User configures prefix via Ocean config
- Integration reads all env vars matching prefix
- Follows Ocean's standard config pattern

### Examples

**Kubernetes:**
```yaml
# User creates secret
apiVersion: v1
kind: Secret
metadata:
  name: custom-headers
stringData:
  X-Api-Key: "value"

# User configures envFrom with prefix
envFrom:
  - secretRef:
      name: custom-headers
      prefix: CUSTOM_HEADER_

# User sets config
OCEAN__INTEGRATION__CONFIG__CUSTOM_HEADERS_PREFIX="CUSTOM_HEADER_"
```

**Docker:**
```bash
export OCEAN__INTEGRATION__CONFIG__CUSTOM_HEADERS_PREFIX="CUSTOM_HEADER_"
export CUSTOM_HEADER_X_API_KEY="value"
```

### Pros
- ✅ Follows Ocean config convention exactly
- ✅ User controls the prefix
- ✅ Works everywhere

### Cons
- ❌ Requires users to understand prefix concept
- ❌ Two configs: prefix + env vars

---

## Recommendation

**Option 2: Secret Name → Environment Variables (Auto-prefix)**

### Why?
1. **Simple**: One config field (`customHeadersSecret`)
2. **Unified**: Same approach for all platforms
3. **K8s-friendly**: Users configure `envFrom` (standard K8s pattern)
4. **Docker-friendly**: Users set env vars directly
5. **No chart changes**: Users configure `envFrom` themselves
6. **Auto-prefix**: Derived from secret name automatically

### Implementation Summary
- Config: `customHeadersSecret: "custom-headers"`
- Auto-prefix: `CUSTOM_HEADERS_` (from secret name)
- K8s: User configures `envFrom` with prefix
- Docker/GitHub: User sets env vars with prefix
- Integration: Reads env vars matching prefix

---

## Questions to Resolve

1. **Should we support both secret path AND env vars?** (Option 4)
   - Or just env vars? (Option 2)

2. **Should prefix be auto-generated or configurable?**
   - Auto: Derived from secret name (simpler)
   - Configurable: Separate `customHeadersPrefix` config (more flexible)

3. **Should we keep JSON approach as fallback?**
   - For backward compatibility?
   - Or remove it entirely?

4. **Helm chart integration:**
   - Document manual `envFrom` configuration?
   - Or add optional Helm chart support (if approved)?

---

## Customer Feedback Summary

- **Issue**: Current JSON approach is "confusing" and "two-step config"
- **Preference**: Single secret name approach
- **Constraint**: Should work for K8s, Docker, and GitHub Actions
- **Constraint**: No Helm chart code changes (preferred)

---

## Next Steps

1. Decide on approach (recommendation: Option 2)
2. Implement chosen approach
3. Update documentation with examples for each platform
4. Consider Helm chart support (optional, if approved)

