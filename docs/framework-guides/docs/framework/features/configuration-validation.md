---
title: ✅ Configuration Validation
sidebar_position: 5
---

The Ocean framework provides a convenient way to validate the configuration of an integration.
By validating the configuration, the integration can make sure that the configuration is valid and that it can perform
the tasks it needs to perform before starting to run.

## How to setup configuration type validation

To setup configuration type validation, the integration needs to provide the available configuration and their types
using the `.port/spec.yaml` file.

## Supported configuration types

The Ocean framework supports the following configuration types:
- `string` - Will check if the value is a valid string. For example: `my string`
- `integer` - Will check if the value is a valid integer. For example: `123`
- `boolean` - Will check if the value is a valid boolean. For example: `true`
- `object` - Will check if the value is a valid JSON object. For example: `{"key": "value"}`
- `url` - Will check if the value is a valid URL. For example: `https://www.google.com`

### Example

`.port/spec.yaml`:
```yaml showLineNumbers
...
configurations:
  - name: myBooleanConfig
    type: boolean
    description: My boolean configuration
```

`config.yaml`:
:::danger ❌ Invalid configuration
```yaml showLineNumbers
...
integration:
  ...
  config:
    // highlight-start
    myConfig: 123 # This will fail validation
    // highlight-end
```
:::

:::tip ✅ Valid configuration
```yaml showLineNumbers
...
integration:
  ...
  config:
    // highlight-start
    myConfig: true # This is a valid configuration
    // highlight-end
```
:::