# Blueprint Design Guide

## Property Type Selection

| Data Type | Blueprint Type | Format | Notes |
|-----------|---------------|--------|-------|
| Status/State | `string` | enum | Use `enumColors` for visual distinction |
| URL | `string` | `url` | Renders as clickable link |
| Date/Time | `string` | `date-time` | ISO8601 format |
| Large text | `string` | `markdown` | For README, descriptions |
| Count | `number` | - | |
| List of strings | `array` | - | |
| True/False | `boolean` | - | |

## Enum Colors

Use consistent colors for status meanings:

```json
{
  "status": {
    "type": "string",
    "enum": ["active", "inactive", "pending", "error"],
    "enumColors": {
      "active": "green",
      "inactive": "lightGray",
      "pending": "yellow",
      "error": "red"
    }
  }
}
```

## Relation Design

### Hierarchy Relations (Child -> Parent)

```json
{
  "relations": {
    "repository": {
      "title": "Repository",
      "target": "githubRepository",
      "required": false,
      "many": false
    }
  }
}
```

### Many-to-Many Relations

```json
{
  "relations": {
    "teams": {
      "title": "Teams",
      "target": "team",
      "required": false,
      "many": true
    }
  }
}
```

## Identifier Best Practices

| Source | Identifier Strategy |
|--------|---------------------|
| Numeric ID | `.id | tostring` |
| UUID | `.id` |
| Composite | `"prefix-" + .id` |
| Scoped | `.parent_id + "-" + .id` |

**Avoid:**
- Names (can change)
- URLs (too long)
- Mutable fields

## OOTB vs Optional Properties

**Include in OOTB blueprint:**
- Core identifying properties (name, status, owner)
- Commonly needed metadata (created_at, updated_at)
- Security-relevant fields (severity, vulnerability count)
- Hierarchy markers (parent references)

**Exclude from OOTB (allow via selector):**
- Verbose data (full descriptions, raw configs)
- Rarely used flags
- Properties that 10x data volume
- Computed properties that slow syncs

## Mapping JQ Patterns

### Safe Property Access
```yaml
description: if .description then .description else "" end
```

### Date Conversion (epoch ms to ISO)
```yaml
createdAt: .created_at / 1000 | strftime("%Y-%m-%dT%H:%M:%SZ")
```

### Array Extraction
```yaml
tags: '[.labels[].name]'
```

### Conditional Status
```yaml
status: if .merged_at then "merged" elif .closed_at then "closed" else "open" end
```

### Nested Object Access
```yaml
owner: .owner.login
```

## Example Complete Blueprint

```json
{
  "identifier": "serviceFinding",
  "title": "Security Finding",
  "icon": "Alert",
  "schema": {
    "properties": {
      "severity": {
        "type": "string",
        "title": "Severity",
        "enum": ["critical", "high", "medium", "low", "info"],
        "enumColors": {
          "critical": "red",
          "high": "orange",
          "medium": "yellow",
          "low": "blue",
          "info": "lightGray"
        }
      },
      "status": {
        "type": "string",
        "title": "Status",
        "enum": ["open", "resolved", "suppressed"],
        "enumColors": {
          "open": "red",
          "resolved": "green",
          "suppressed": "lightGray"
        }
      },
      "title": {
        "type": "string",
        "title": "Title"
      },
      "link": {
        "type": "string",
        "format": "url",
        "title": "Link"
      },
      "detectedAt": {
        "type": "string",
        "format": "date-time",
        "title": "Detected At"
      }
    },
    "required": []
  },
  "relations": {
    "service": {
      "title": "Service",
      "target": "service",
      "required": false,
      "many": false
    }
  }
}
```
