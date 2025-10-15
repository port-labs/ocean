---
title: Integration Configuration and Kinds in Ocean
sidebar_label: 🏗️ Integration Configuration and Kinds in Ocean
sidebar_position: 5
---

# 🏗️ Integration Configuration and Kinds in Ocean

When building an integration, you'll need to define how your data is structured and what configurations users can provide. In Ocean, we use "kinds" to categorize different types of data (like projects, issues, or any other resource type from your service). These kinds might require different filters, fields or other parameters to bring the data into Port. This custom inputs are collected through the mapping configuration by overriding the configuration classes in ocean in the `integration.py` file.

:::tip Configuration is Optional
The configuration system described in this guide is only required if your integration needs custom configuration fields in the mapping. You can skip this entire section if:
1. Your integration has a fixed set of resources
2. You don't need user-defined parameters like filters, fields, or other parameters in the mapping configuration
3. Your API calls don't require custom configuration like metrics, tags and other parameters
4. You're using standard endpoints with fixed parameters

In these cases, you can focus on implementing the core functionality of your integration without worrying about configuration management.
:::

In this guide, we will learn how to configure the integration and accept user-defined configurations for the kinds. We will:
- Define **Selectors**: classes that store the user-defined parameters for each kind (e.g., JQL query, fields, expand parameters).
- Define **ResourceConfigs**: classes that associate a Selector with a particular kind ("issue" or "project").
- Combine these into a **PortAppConfig**, which describes the overall integration configuration for Ocean.

## Core Concepts

### Understanding Selectors

A `Selector` is a configuration class that defines what parameters users can provide for a specific kind of resource. Think of it as a form that users fill out to customize how the integration will interact with the third-party service for the given kind. To create a selector, you need to subclass the `Selector` class from `port_ocean.core.handlers.port_app_config.models` and define the parameters that users can provide.

Key aspects of Selectors:
- **User Input**: Defines what parameters users can configure
- **Validation**: Ensures user input is valid
- **Defaults**: Provides sensible default values
- **Documentation**: Describes each parameter's purpose
- **Alias**: Allows users to specify the parameter name in the mapping configuration

Example:
```python
class IssueSelector(Selector):
    filter_query: str | None = None
    # Users can specify which fields to retrieve
    fields: str | None = Field(
        description="Additional fields to be included in the API response",
        default="*all",
    )
```

### Understanding ResourceConfig

A `ResourceConfig` links a `Selector` to a specific kind of resource in your integration. It's the bridge between user configuration and the actual data structure.

Key aspects of ResourceConfig:
- **Kind Association**: Links a Selector to a specific resource type
- **Type Safety**: Uses Literal types to ensure kind names are consistent
- **Configuration Binding**: Combines user input with resource definition

Example:
```python
class IssueConfig(ResourceConfig):
    selector: IssueSelector  # The user's configuration
    kind: Literal["issue"]   # The resource type
```

### Why This Structure?

This three-layer structure (Selector → ResourceConfig → PortAppConfig) provides:

1. **Separation of Concerns**:
   - Selectors handle user input
   - ResourceConfigs handle resource definitions
   - PortAppConfig handles overall integration structure

2. **Flexibility**:
   - Easy to add new resource types
   - Easy to modify configuration options
   - Easy to maintain backward compatibility

3. **Maintainability**:
   - Clear separation of configuration from implementation
   - Easy to understand and modify
   - Self-documenting structure

:::tip Best Practice
When designing your configuration structure:
1. Start with the user's needs - what parameters do they need to configure?
2. Create Selectors that capture these parameters
3. Create ResourceConfigs that link Selectors to your resource types
4. Combine everything in a PortAppConfig
:::


### Understanding the PortAppConfig

The **`PortAppConfig`** class groups all resource configurations:

```python
class MyIntegrationPortAppConfig(PortAppConfig):
    resources: list[
        IssueConfig
        | ProjectResourceConfig
        | ResourceConfig
    ]
```

- The `resources` field can include any combination of your resource configs
- Include a generic `ResourceConfig` for fallback cases

### The Integration Class
The integration class is the entry point for the integration. It is responsible for loading the configuration and setting up the integration. Ocean automatically reads this from the `integration.py` file in your integration's root directory:

```python
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig

class MyIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = MyIntegrationPortAppConfig
```

This tells Ocean how to handle the config at runtime. When users update the config from the UI, Ocean uses your `PortAppConfig` to validate and store those values.


## Putting It All Together

To add the integration configuration follow the steps below:

- Create the `integration.py` file in your integration directory:
    ```bash
    $ touch my_integration/integration.py
    ```
- Create the `Selector` class in the `integration.py` file, this class will contain the custom fields that will be used to filter the data from the third-party service
- Create the `ResourceConfig` class in the `integration.py` file, this class will contain the `selector` field that will include the `Selector` class and the `kind` field that will include the kind of the resource
- Create the `PortAppConfig` class in the `integration.py` file, this class will contain the `resources` field that will include all the `ResourceConfig` classes
- Create the custom integration class that subclasses `BaseIntegration` and sets the `AppConfigHandlerClass` `CONFIG_CLASS` to your integration's `PortAppConfig` class:
    ```python
    class MyIntegration(BaseIntegration):
        class AppConfigHandlerClass(APIPortAppConfig):
            CONFIG_CLASS = MyIntegrationPortAppConfig
    ```



## Guidelines for Defining Integration Configuration

- **Provide Defaults**: Always provide sensible default values for configuration fields
- **Add Descriptions**: Include field descriptions to help users understand the configuration options
- **Single File**: Keep all configurations in one file for better maintainability
- **Avoid Nested Classes**: Keep configuration classes at the module level
- **Type Safety**: Use type hints and Pydantic for validation
- **Documentation**: Add clear descriptions for each configuration option

:::info Example Implementation
You can find a complete example in the [Jira integration](https://github.com/port-labs/ocean/tree/main/integrations/jira), which demonstrates these concepts in practice.
:::

Next, we'll learn how to define important configurations such as specs, blueprints, and mapping configurations to help ingest data into Port.
