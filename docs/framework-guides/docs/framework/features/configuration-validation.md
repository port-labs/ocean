---
title: Configuration Validation
sidebar_label: ✅ Configuration Validation
sidebar_position: 7
description: Use Ocean to validate integration inputs before startup
---

# ✅ Configuration Validation

The Ocean framework provides a convenient way to validate the configuration of an integration.

By providing a validation specification (provided in the [`spec.yml`](../../developing-an-integration/defining-configuration-files.md#the-specyaml-file) file), the Ocean framework can verify that the configuration provided to the integration contains all required parameters in the expected format, ensuring it can start and perform its logic.

Ocean performs configuration validation based on the specification provided in the `.port/spec.yml` file.

## How to setup configuration type validation

To setup configuration type validation, the integration needs to provide the available inputs and their types
using the `.port/spec.yaml` file.

## Supported parameter configuration types

The Ocean framework supports the following configuration types:

- `string` - Will check if the value is a valid string. For example: `my string`
- `integer` - Will check if the value is a valid integer. For example: `123`
- `boolean` - Will check if the value is a valid boolean. For example: `true`
- `object` - Will check if the value is a valid JSON object. For example: `{"key": "value"}`
- `url` - Will check if the value is a valid URL. For example: `https://www.google.com`

### Example

```yaml showLineNumbers title=".port/spec.yml"
configurations:
  - name: myBooleanParameter
    type: boolean
    description: My boolean parameter
```

:::danger ❌ Invalid configuration

```yaml showLineNumbers title="config.yml"
...
integration:
  ...
  config:
    // highlight-next-line
    myBooleanParameter: 123 # This will fail validation
```

:::

:::tip ✅ Valid configuration

```yaml showLineNumbers title="config.yml"
...
integration:
  ...
  config:
    // highlight-next-line
    myBooleanParameter: true # This is a valid configuration
```

:::
