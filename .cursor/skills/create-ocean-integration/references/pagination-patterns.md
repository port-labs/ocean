# Pagination Patterns

## Pattern 1: Offset-Based (Most Common)

Use when API supports `limit` + `offset` or `pageNumber` + `pageSize`.

```python
async def _send_offset_paginated_request(
    self,
    endpoint: str,
    params: Optional[Dict] = None,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    page_number = 0
    params = params or {}
    
    while True:
        request_params = {
            **params,
            "pageNumber": page_number,
            "pageSize": self.PAGE_SIZE,
        }
        
        response = await self.send_api_request(endpoint, params=request_params)
        
        items = response.get("content", [])
        if not items:
            break
            
        yield items
        
        if response.get("last", True):
            break
        page_number += 1
```

## Pattern 2: Cursor-Based

Use when API returns a cursor/afterKey for next page.

```python
async def _send_cursor_paginated_request(
    self,
    endpoint: str,
    params: Optional[Dict] = None,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    params = params or {}
    after_key: Optional[str] = None
    
    while True:
        request_params = {**params, "size": self.PAGE_SIZE}
        if after_key:
            request_params["afterKey"] = after_key
        
        response = await self.send_api_request(endpoint, params=request_params)
        
        items = response.get("data", {}).get("items", [])
        if not items:
            break
            
        yield items
        
        after_key = response.get("data", {}).get("afterKey")
        if not after_key or after_key < 0:
            break
```

## Pattern 3: Link Header (GitHub-style)

Use when API returns pagination links in HTTP headers.

```python
import re

NEXT_LINK_PATTERN = re.compile(r'<([^>]+)>;\s*rel="next"')

async def send_paginated_request(
    self,
    resource: str,
    params: Optional[Dict] = None,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    params = params or {}
    params["per_page"] = self.PAGE_SIZE
    
    while True:
        response = await self.make_request(resource, params=params)
        
        if not response or not (items := response.json()):
            break
            
        yield items
        
        link_header = response.headers.get("Link", "")
        match = NEXT_LINK_PATTERN.search(link_header)
        if not match:
            break
            
        resource = match.group(1)
        params = None  # Next URL is complete
```

## Pattern 4: GraphQL Cursor

Use for GraphQL APIs with connection pattern.

```python
async def send_graphql_paginated_request(
    self,
    query: str,
    variables: Dict,
    connection_path: str,  # e.g., "organization.repositories"
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    cursor = None
    
    while True:
        vars = {**variables, "first": self.PAGE_SIZE}
        if cursor:
            vars["after"] = cursor
        
        response = await self.execute_query(query, vars)
        
        # Navigate to connection using path
        connection = self._get_nested(response, connection_path)
        nodes = connection.get("nodes", [])
        
        if not nodes:
            break
            
        yield nodes
        
        page_info = connection.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
```

## Choosing Pagination Pattern

| API Response Characteristic | Pattern to Use |
|---------------------------|----------------|
| Returns `offset`/`limit` or `page`/`pageSize` | Offset-based |
| Returns `afterKey`, `cursor`, or `nextToken` | Cursor-based |
| Returns `Link` header with rel="next" | Link header |
| GraphQL with `pageInfo.hasNextPage` | GraphQL cursor |
| Returns `pages_number` or `totalPages` | Page-number based |
