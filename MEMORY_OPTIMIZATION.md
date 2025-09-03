# Memory Optimization for itemsToParse

## Problem

When using `itemsToParse` in Ocean integrations, the original payload data is embedded into each generated object, causing significant memory amplification. For example:
- A 1MB payload with 1000 items to parse becomes ~1GB in memory (1000 × 1MB)
- This is further amplified by concurrent mapping and JQ stringification (~3x input size)
- In memory-constrained environments (1GB), large files (20MB+) can cause OOM crashes during resync

## Solution

A new per-kind configuration option `embedOriginalData` allows users to control whether the original payload is embedded when using `itemsToParse`.

### Configuration

#### Per-Kind Configuration (Recommended)
```yaml
resources:
  - kind: myKind
    selector:
      query: "true"
    port:
      itemsToParse: .items
      embedOriginalData: false  # Prevents OOM by not embedding original data
      entity:
        mappings:
          identifier: .item.id
          title: .item.name
```

#### Global Default
```yaml
# In integration configuration
embed_original_data_in_items_to_parse: false  # Default: true for backward compatibility
```

### Backward Compatibility

- **Default behavior**: `embedOriginalData` defaults to `null`, which uses the global setting
- **Global default**: `embed_original_data_in_items_to_parse` defaults to `true` for backward compatibility
- **Existing integrations**: Continue to work without changes

### When to Use

**Set `embedOriginalData: false` when:**
- You only need data from the parsed items (not the original payload)
- Working with large payloads that cause memory issues
- Running in memory-constrained environments

**Keep `embedOriginalData: true` when:**
- Your entity mappings reference both item data (`.item.field`) and original payload data (`.metadata.field`)
- Memory usage is not a concern

### Examples

#### Before (Memory Intensive)
```yaml
port:
  itemsToParse: .applications
  entity:
    mappings:
      identifier: .item.id                    # Uses item data
      title: .item.name                       # Uses item data
      environment: .cluster.environment       # Uses original payload data
```

#### After (Memory Optimized)
```yaml
port:
  itemsToParse: .applications
  embedOriginalData: false
  entity:
    mappings:
      identifier: .item.id                    # Uses item data
      title: .item.name                       # Uses item data
      # environment: .cluster.environment     # Would fail - original data not available
```

If you need both item and original data, consider restructuring your data source or keeping `embedOriginalData: true` for those specific kinds.

## Impact

- **High severity**: Prevents OOM crashes in production deployments
- **Memory reduction**: Can reduce memory usage by 10x-100x depending on payload structure
- **Backward compatible**: Existing integrations continue working unchanged
- **Configurable**: Users can opt-in per kind based on their specific needs