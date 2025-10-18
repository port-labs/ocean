# Zendesk Integration Example

This example demonstrates how to integrate Zendesk with Port using the HTTP Server integration. It showcases several advanced features:

## Features Demonstrated

### 1. **Cursor-Based Pagination**
Zendesk uses cursor pagination to handle large datasets without the typical 10,000 record limit of offset pagination. This example shows how to configure:
- Cursor query parameters (`page[after]`, `page[size]`)
- Response paths for cursor extraction (`meta.after_cursor`)
- Has-more detection (`meta.has_more`)

### 2. **Data Path Extraction**
Zendesk wraps API responses in nested objects. The `data_path` feature extracts the actual data arrays:
```yaml
data_path: .tickets  # Extracts the tickets array from {"tickets": [...], "meta": {...}}
```

### 3. **Path Parameters & Dynamic Endpoint Resolution**
The integration automatically resolves path parameters for nested resources. For example, fetching ticket comments:

```yaml
kind: /api/v2/tickets/{ticket_id}/comments.json
path_parameters:
  ticket_id:
    endpoint: /api/v2/tickets.json
    method: GET
    field: .id | tostring
    filter: 'true'
```

The integration:
1. Queries `/api/v2/tickets.json` to get all ticket IDs
2. Resolves each `{ticket_id}` placeholder
3. Calls `/api/v2/tickets/123/comments.json` for each ticket
4. Injects `__ticket_id` into each comment entity for use in mappings

### 4. **Basic Authentication with Special Format**
Zendesk requires a unique username format for API token authentication:
```
username: your-email@domain.com/token
password: your_api_token
```

## Files Included

- **`blueprints.json`** - Port blueprints for Zendesk entities (Organizations, Users, Tickets, Comments)
- **`port-app-config.yml`** - Resource mappings and configuration
- **`installation.md`** - Installation commands for Docker, Helm, Kubernetes, and Docker Compose

## Quick Start

1. **Import the blueprints** into Port (via UI or API)
2. **Choose an installation method** from `installation.md`
3. **Update the configuration** with your Zendesk subdomain and credentials
4. **Deploy** and the integration will start syncing data

## Data Model

```
zendesk_organization
    ↓
zendesk_user
    ↓
zendesk_ticket
    ↓
zendesk_comment → (relates to ticket and author)
```

## API Endpoints Mapped

- `/api/v2/organizations.json` → `zendesk_organization`
- `/api/v2/users.json` → `zendesk_user`
- `/api/v2/tickets.json` → `zendesk_ticket`
- `/api/v2/tickets/{ticket_id}/comments.json` → `zendesk_comment`

## Learn More

- [Zendesk API Documentation](https://developer.zendesk.com/api-reference/)
- [Port HTTP Server Integration](../../README.md)
- [Ocean Framework Documentation](https://ocean.getport.io/)

