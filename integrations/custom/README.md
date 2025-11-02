# Ocean Custom Integration

An Ocean integration that can connect to any HTTP REST API with configurable authentication, pagination, and data mapping.

## Overview

This integration allows Port customers to connect to any custom API, internal system, or HTTP service without requiring custom development. Each integration instance connects to one API backend, and users can map multiple endpoints through standard Ocean resource configuration.

## Quick Start

### 1. Install the Integration

Using Docker:
```bash
docker run -d \
  -e OCEAN__PORT__CLIENT_ID="your-port-client-id" \
  -e OCEAN__PORT__CLIENT_SECRET="your-port-client-secret" \
  -e OCEAN__INTEGRATION__CONFIG__BASE_URL="https://api.example.com" \
  -e OCEAN__INTEGRATION__CONFIG__AUTH_TYPE="bearer_token" \
  -e OCEAN__INTEGRATION__CONFIG__API_TOKEN="your-api-token" \
  -e OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE="offset" \
  ghcr.io/port-labs/port-ocean-custom:0.1.5-dev
```

### 2. Configure Your Endpoints

Create a mapping in Port's UI or via API:
```yaml
resources:
  - kind: /api/v1/users
    selector:
      query: 'true'
      data_path: '.users'
    port:
      entity:
        mappings:
          identifier: .id
          title: .name
          blueprint: '"user"'
          properties:
            email: .email
```

### 3. Sync Your Data

The integration will automatically sync data from your API to Port!

> 💡 **Pro Tip**: Use the [Custom API Integration Wizard](https://github.com/port-labs/custom-api-integration-wizard) to automatically generate blueprints and mappings for your API!

## Features

- **Universal HTTP Connectivity** - Works with any REST API
- **Multiple Authentication Methods** - Bearer token, Basic auth, API key, or none
- **Flexible Pagination** - Offset/limit, page/size, cursor-based, or none
- **Dynamic Path Parameters** - Query APIs to discover parameter values for nested endpoints
- **Endpoint-as-Kind** - Each endpoint tracked separately in Port's UI for better testing and debugging
- **Smart Data Extraction** - Use JQ `data_path` to extract arrays from any response structure
- **Built-in Caching & Rate Limiting** - Leverages Ocean's framework for optimal performance
- **Standard Ocean Mapping** - Uses JQ for data transformation
- **Configurable per Installation** - One integration per API backend

## Installation Configuration

Configure the integration through environment variables when installing:

### Required Configuration

```bash
# API Backend URL
OCEAN__INTEGRATION__CONFIG__BASE_URL=https://api.example.com

# Authentication (choose one method)
OCEAN__INTEGRATION__CONFIG__AUTH_TYPE=bearer_token
OCEAN__INTEGRATION__CONFIG__API_TOKEN=your-token-here
```

### Authentication Methods

#### Bearer Token
```bash
OCEAN__INTEGRATION__CONFIG__AUTH_TYPE=bearer_token
OCEAN__INTEGRATION__CONFIG__API_TOKEN=your-token-here
```

#### Basic Authentication
```bash
OCEAN__INTEGRATION__CONFIG__AUTH_TYPE=basic
OCEAN__INTEGRATION__CONFIG__USERNAME=your-username
OCEAN__INTEGRATION__CONFIG__PASSWORD=your-password
```

#### API Key (Header)
```bash
OCEAN__INTEGRATION__CONFIG__AUTH_TYPE=api_key
OCEAN__INTEGRATION__CONFIG__API_KEY=your-api-key
OCEAN__INTEGRATION__CONFIG__API_KEY_HEADER=X-API-Key  # Optional, defaults to X-API-Key
```

#### No Authentication
```bash
OCEAN__INTEGRATION__CONFIG__AUTH_TYPE=none
```

### Pagination Configuration

```bash
# Pagination method
OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE=offset  # offset, page, cursor, or none

# Page size (applies to all pagination types)
OCEAN__INTEGRATION__CONFIG__PAGE_SIZE=100

# Optional: Custom parameter names for offset pagination
OCEAN__INTEGRATION__CONFIG__OFFSET_PARAM=offset    # Default: "offset"
OCEAN__INTEGRATION__CONFIG__LIMIT_PARAM=limit      # Default: "limit"

# Optional: Custom parameter names for page pagination  
OCEAN__INTEGRATION__CONFIG__PAGE_PARAM=page        # Default: "page"
OCEAN__INTEGRATION__CONFIG__SIZE_PARAM=size        # Default: "size"
OCEAN__INTEGRATION__CONFIG__START_PAGE=1           # Default: 1

# Optional: Custom parameter names for cursor pagination
OCEAN__INTEGRATION__CONFIG__CURSOR_PARAM=cursor    # Default: "cursor"
OCEAN__INTEGRATION__CONFIG__LIMIT_PARAM=limit      # Default: "limit"
```

### Optional Configuration

```bash
# Request timeout in seconds
OCEAN__INTEGRATION__CONFIG__TIMEOUT=30

# SSL verification
OCEAN__INTEGRATION__CONFIG__VERIFY_SSL=true

# Rate limiting (concurrent requests)
OCEAN__INTEGRATION__CONFIG__MAX_CONCURRENT_REQUESTS=10
```

## Resource Mapping

Define API endpoints in your `resources.yaml` file. Each resource block represents one API endpoint.

### 🆕 Endpoint-as-Kind Feature

**The `kind` field is now the endpoint path itself!** This provides better visibility in Port's UI, allowing you to:
- Track each endpoint's sync status individually
- Debug mapping issues per endpoint
- Monitor data ingestion per API call

```yaml
resources:
  # Kind is the endpoint path - provides granular tracking in Port
  - kind: /api/v1/users
    selector:
      query: 'true'  # JQ filter for entities
      method: GET    # Optional, defaults to GET
      query_params:  # Optional query parameters
        active: "true"
        department: "engineering"
      headers:       # Optional additional headers
        Accept: "application/json"
      data_path: '.users'  # JQ path to extract data array from response
    port:
      entity:
        mappings:
          identifier: .id
          title: .name
          blueprint: '"user"'
          properties:
            email: .email
            department: .department
            active: .is_active
            created: .created_at

  # Another endpoint with different kind
  - kind: /api/v1/projects
    selector:
      query: 'true'
      query_params:
        status: "active"
      data_path: '.data.projects'  # Nested data extraction
    port:
      entity:
        mappings:
          identifier: .project_id
          title: .project_name
          blueprint: '"project"'
          properties:
            description: .description
            owner: .owner.email
            budget: .budget_amount
            created: .created_date
```

### Legacy Format (Still Supported)

The old format with `kind: api_resource` and fields inside `selector.query` is still supported for backward compatibility:

```yaml
resources:
  - kind: api_resource
    selector:
      query:
        endpoint: "/api/v1/users"
        method: "GET"
    port:
      entity:
        mappings:
          identifier: .id
          title: .name
```

## Data Extraction with `data_path`

### 🆕 Smart Data Extraction

Use the `data_path` field in your selector to extract data arrays from any response structure using JQ expressions:

```yaml
selector:
  data_path: '.members'  # Extract array from response
```

### Common Response Formats

#### Direct Array Response
```json
[
  {"id": 1, "name": "User 1"},
  {"id": 2, "name": "User 2"}
]
```
**Mapping:** No `data_path` needed - array is returned directly

#### Wrapped Data Array
```json
{
  "data": [
    {"id": 1, "name": "User 1"},
    {"id": 2, "name": "User 2"}
  ],
  "pagination": {"total": 100}
}
```
**Mapping:** `data_path: '.data'`

#### Nested Data Structure
```json
{
  "response": {
    "users": {
      "items": [
        {"id": 1, "name": "User 1"}
      ]
    }
  }
}
```
**Mapping:** `data_path: '.response.users.items'`

#### API-Specific Keys (e.g., Microsoft Graph)
```json
{
  "value": [
    {"id": 1, "name": "User 1"}
  ],
  "@odata.nextLink": "..."
}
```
**Mapping:** `data_path: '.value'`

#### Slack-style Response
```json
{
  "ok": true,
  "members": [
    {"id": "U123", "name": "John"}
  ]
}
```
**Mapping:** `data_path: '.members'`

### Benefits of `data_path`

- **Simplified Mappings**: No need for `.item.` prefix in property mappings
- **Flexible**: Works with any response structure
- **Clear**: Explicitly shows where data comes from
- **Powerful**: Full JQ expression support for complex extractions

## Pagination Support

### Offset/Limit Pagination
```yaml
# Integration config:
OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE=offset
OCEAN__INTEGRATION__CONFIG__PAGE_SIZE=50

# Requests made:
GET /api/v1/users?offset=0&limit=50
GET /api/v1/users?offset=50&limit=50
# ... continues until no more data
```

### Page/Size Pagination  
```yaml
# Integration config:
OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE=page
OCEAN__INTEGRATION__CONFIG__PAGE_SIZE=25
OCEAN__INTEGRATION__CONFIG__START_PAGE=1

# Requests made:
GET /api/v1/users?page=1&size=25
GET /api/v1/users?page=2&size=25  
# ... continues until no more data
```

### Cursor-Based Pagination
```yaml
# Integration config:
OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE=cursor
OCEAN__INTEGRATION__CONFIG__PAGE_SIZE=20

# Requests made:
GET /api/v1/users?limit=20
GET /api/v1/users?cursor=xyz123&limit=20
# ... continues until no next_cursor
```

Expected response format:
```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "xyz123",
    "has_more": true
  }
}
```

### No Pagination
```yaml
# Integration config:
OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE=none

# Single request made:
GET /api/v1/users
```

## Dynamic Path Parameters

The HTTP Server integration supports dynamic path parameters, allowing you to use one API endpoint to discover parameter values for another endpoint. This is perfect for APIs with nested resources like `/api/users/{user_id}/projects`.

### Basic Configuration

```yaml
resources:
  # Kind is the endpoint template with parameters
  - kind: /api/v1/users/{user_id}/projects
    selector:
      query: "true"
      method: GET
      path_parameters:
        user_id:
          endpoint: "/api/v1/users"          # Discovery endpoint
          field: ".user_id"                  # JQ: extract parameter value
          filter: ".is_active == true"       # JQ: filter which records to use
      query_params:
        limit: "50"
      data_path: '.projects'
    port:
      entity:
        mappings:
          identifier: .id
          title: .name
          blueprint: '"project"'
```

### How It Works

1. **Discovery**: Calls `GET /api/v1/users` to get all users
2. **Filter**: Applies `.is_active == true` to each user record
3. **Extract**: Uses `.user_id` to get parameter values like `["user_001", "user_002"]`
4. **Generate**: Creates URLs like `/api/v1/users/user_001/projects`, `/api/v1/users/user_002/projects`
5. **Fetch**: Calls each generated URL and ingests the data

### Advanced Examples

#### Complex Field Extraction
```yaml
path_parameters:
  team_slug:
    endpoint: "/api/v1/teams"
    # Transform team name to URL-safe slug
    field: '.name | ascii_downcase | gsub(" "; "-")'
    filter: '.member_count > 5'
```

#### Discovery with Query Parameters
```yaml
path_parameters:
  dept_id:
    endpoint: "/api/v1/departments"
    query_params:
      active: "true"
      include_metrics: "true"
    field: ".department_id"
    filter: '.budget > 100000 and .team_size > 10'
```

#### Multiple Filters
```yaml
path_parameters:
  project_id:
    endpoint: "/api/v1/projects"
    field: ".project_id"
    filter: '.status == "active" and .created_at > "2024-01-01" and (.tags | contains(["production"]))'
```

### Benefits

- **Self-Contained**: No dependency on Port entities - uses API data directly
- **Flexible**: Full JQ power for filtering and field extraction
- **Efficient**: Can optimize discovery calls with query parameters
- **Dynamic**: Automatically adapts when new entities are added to the API

## Example Use Cases

### Internal HR System
```yaml
# Integration config
OCEAN__INTEGRATION__CONFIG__BASE_URL=https://hr.company.com
OCEAN__INTEGRATION__CONFIG__AUTH_TYPE=bearer_token
OCEAN__INTEGRATION__CONFIG__API_TOKEN=hr-token-123
OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE=offset

# Resource mapping
resources:
  - kind: api_resource
    selector:
      query:
        endpoint: "/api/employees"
        query_params:
          status: "active"
    port:
      entity:
        mappings:
          identifier: .employee_id
          title: .full_name
          properties:
            email: .email
            department: .dept
            hire_date: .hired_on
```

### Custom Project Management Tool
```yaml
# Integration config  
OCEAN__INTEGRATION__CONFIG__BASE_URL=https://projects.internal.com
OCEAN__INTEGRATION__CONFIG__AUTH_TYPE=api_key
OCEAN__INTEGRATION__CONFIG__API_KEY=proj-key-456
OCEAN__INTEGRATION__CONFIG__API_KEY_HEADER=Authorization
OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE=page

# Resource mapping
resources:
  - kind: api_resource
    selector:
      query:
        endpoint: "/projects"
        headers:
          X-Version: "v2"
    port:
      entity:
        mappings:
          identifier: .id
          title: .name
          properties:
            status: .current_status
            lead: .project_lead.name
            budget: .allocated_budget
```

### Legacy ERP System
```yaml
# Integration config
OCEAN__INTEGRATION__CONFIG__BASE_URL=https://erp.legacy.com
OCEAN__INTEGRATION__CONFIG__AUTH_TYPE=basic
OCEAN__INTEGRATION__CONFIG__USERNAME=api_user
OCEAN__INTEGRATION__CONFIG__PASSWORD=api_pass
OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE=none

# Resource mapping  
resources:
  - kind: api_resource
    selector:
      query:
        endpoint: "/erp/resources"
        method: "POST"
        query_params:
          format: "json"
          active_only: "1"
    port:
      entity:
        mappings:
          identifier: .resource_code
          title: .resource_name
          properties:
            type: .resource_type
            cost_center: .cost_center_id
            status: .status_code
```

## Testing

Use the provided test HTTP server to validate your configuration:

1. **Start the test server:**
   ```bash
   cd /path/to/test-http-server
   python main.py --auth bearer --pagination offset --port 8080
   ```

2. **Configure the integration:**
   ```bash
   OCEAN__INTEGRATION__CONFIG__BASE_URL=http://localhost:8080
   OCEAN__INTEGRATION__CONFIG__AUTH_TYPE=bearer_token
   OCEAN__INTEGRATION__CONFIG__API_TOKEN=test-token-123
   OCEAN__INTEGRATION__CONFIG__PAGINATION_TYPE=offset
   ```

3. **Test with sample resources:**
   ```yaml
   resources:
     - kind: api_resource
       selector:
         query:
           endpoint: "/api/v1/users"
       port:
         entity:
           mappings:
             identifier: .id
             title: .name
             properties:
               email: .email
               active: .is_active
   ```

## Development

### Running Locally
```bash
cd integrations/http-server
poetry install
poetry run python debug.py
```

### Adding New Features
The integration follows standard Ocean patterns:
- Authentication logic in `http_server/client.py`
- Configuration models in `integration.py` 
- Resync handlers in `main.py`
- Client factory in `initialize_client.py`

## Troubleshooting

### Common Issues

1. **Authentication Errors (401)**
   - Verify `AUTH_TYPE` matches your API requirements
   - Check token/credentials are correct
   - Ensure API key header name matches API expectations

2. **No Data Returned**
   - Check endpoint URL is correct
   - Verify response format contains expected data keys
   - Test endpoint manually with curl/Postman

3. **Pagination Not Working**
   - Verify pagination type matches API pattern
   - Check parameter names match API expectations
   - Review API documentation for pagination format

4. **SSL/TLS Errors**
   - Set `VERIFY_SSL=false` for self-signed certificates
   - Check certificate chain is valid

### Debugging

Enable debug logging to see detailed request/response information:

```bash
OCEAN__LOG_LEVEL=DEBUG python debug.py
```

This will show:
- HTTP requests being made
- Response status codes and data
- Pagination logic flow
- Data extraction process

## Support

For issues or questions:
1. Check the [Ocean Integration Documentation](https://ocean.getport.io/)
2. Review API logs for detailed error information  
3. Test endpoints manually to verify API behavior
4. Contact Port support with integration logs






