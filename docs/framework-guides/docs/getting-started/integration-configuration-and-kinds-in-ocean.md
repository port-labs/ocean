---
sidebar_position: 3
---

# 🏗️ Integration Configuration and Kinds in Ocean
With the API client implemented, you will notice we are exporting two types of data, namely projects and issues. In Ocean, these are referred to as kinds. Kinds are a way to categorize data in Ocean. They are used to define the structure of the data that is being exported.

In addition, you often want users to specify certain **parameters** in the integration, such as JQL filters for issues or expansion parameters for projects. These configurations let users filter or refine the data they retrieve from Jira.

In this guide, we will learn how to configure the integration and accept user-defined configurations for the kinds. We will:

- Define **Selectors**: classes that store the user-defined parameters for each kind (e.g., JQL query, fields, expand parameters).
- Define **ResourceConfigs**: classes that associate a Selector with a particular kind (“issue” or “project”).
- Combine these into a **PortAppConfig**, which describes the overall integration configuration for Ocean.

## Integration Configuration

Create an `overrides.py` file in the same directory as your `client.py`:

```
$ touch jira/overrides.py
```

This file will:

1. Contain **Selector** subclasses for issues and projects.
2. Contain corresponding **ResourceConfig** classes, linking each Selector to a specific kind.
3. Define a **PortAppConfig** to consolidate all resource configurations.

Configurations in Ocean are powered by Python type-hints and [Pydantic](https://docs.pydantic.dev/latest/). This approach provides:

- **Validation**: Ensuring user inputs (like JQL strings) are valid.
- **Schema**: Defining how data is structured and stored.

## Selector Subclasses

A **Selector** class holds the parameters that a user can provide for a given kind. For Jira, the two major kinds we care about are **issues** and **projects**. Below, you’ll see how we capture a user’s JQL query or additional fields for issues, and the `expand` parameter for projects.


<details>

<summary><b>Selectors (Click to expand)</b></summary>

```python showLineNumbers
from typing import Literal

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class JiraIssueSelector(Selector):
    jql: str | None = None
    fields: str | None = Field(
        description="Additional fields to be included in the API response",
        default="*all",
    )


class JiraProjectSelector(Selector):
    expand: str = Field(
        description="A comma-separated list of the parameters to expand.",
        default="insight",
    )

```

</details>

### Explanation

- **`JiraIssueSelector`**: Allows users to specify a JQL filter (`jql`) and which fields to retrieve (`fields`).
- **`JiraProjectSelector`**: Lets users set an `expand` parameter if they want additional details (e.g., `insight`).

## ResourceConfig Classes

**ResourceConfig** ties a Selector to a particular **kind**. In Jira’s case, we have two kinds: `"issue"` and `"project"`.


<details>

<summary><b>ResourceConfigs (Click to expand)</b></summary>

```python showLineNumbers
class JiraIssueConfig(ResourceConfig):
    selector: JiraIssueSelector
    kind: Literal["issue"]


class JiraProjectResourceConfig(ResourceConfig):
    selector: JiraProjectSelector
    kind: Literal["project"]

```

</details>

### Explanation

- **`JiraIssueConfig`**: Expects a `JiraIssueSelector` for user-defined parameters, and identifies the kind as `"issue"`.
- **`JiraProjectResourceConfig`**: Expects a `JiraProjectSelector`, with kind `"project"`.

## Defining the PortAppConfig

The **`PortAppConfig`** class groups multiple resource configurations into a single config object. It’s where you specify all the possible ResourceConfigs that your integration supports.


<details>

<summary><b>PortAppConfig (Click to expand)</b></summary>

```python showLineNumbers
class JiraPortAppConfig(PortAppConfig):
    resources: list[
        JiraIssueConfig
        | JiraProjectResourceConfig
        | ResourceConfig
    ]
```

</details>

### Explanation

- The `resources` field can include any combination of `JiraIssueConfig` or `JiraProjectResourceConfig`, as well as a generic `ResourceConfig` if you need to handle unexpected or fallback cases.

## The `integration.py` file

Having defined these configurations, we need to expose them to Ocean. Ocean automatically grabs configurations from a special file defined in the root folder of the integration itself, `integration.py`. This file should contain a class which subclasses `port_ocean.core.integrations.base.BaseIntegration` and ties the configurations together.


<details>

<summary><b>integration.py (Click to expand)</b></summary>

```python showLineNumbers
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig

class JiraIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = JiraPortAppConfig
```

</details>

This tells Ocean how to handle the config at runtime. Whenever users update the config from the UI, Ocean uses JiraPortAppConfig to validate and store those values.

## Conclusion

With this, you have:

- Created **Selector** classes (`JiraIssueSelector`, `JiraProjectSelector`) to handle user-defined inputs for issues and projects.
- Built **ResourceConfig** classes (`JiraIssueConfig`, `JiraProjectResourceConfig`) that define each kind in Ocean.
- Combined them into a **`JiraPortAppConfig`** to hold all resources.

With these configurations, you can now accept user-specific parameters (like JQL strings) and expansions for projects. This sets the stage for actually **retrieving** and **exporting** your Jira issues and projects into Ocean using the **API client** from the previous guide.

Your `jira/overrides.py` file should look like this:


<details>

<summary><b>overrides.py (Click to expand)</b></summary>

```python showLineNumbers
from typing import Literal

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class JiraIssueSelector(Selector):
    jql: str | None = None
    fields: str | None = Field(
        description="Additional fields to be included in the API response",
        default="*all",
    )


class JiraProjectSelector(Selector):
    expand: str = Field(
        description="A comma-separated list of the parameters to expand.",
        default="insight",
    )


class JiraIssueConfig(ResourceConfig):
    selector: JiraIssueSelector
    kind: Literal["issue"]


class JiraProjectResourceConfig(ResourceConfig):
    selector: JiraProjectSelector
    kind: Literal["project"]


class JiraPortAppConfig(PortAppConfig):
    resources: list[
        JiraIssueConfig
        | JiraProjectResourceConfig
        | ResourceConfig
    ]
```

</details>

and your `integration.py` file should look like so:


<details>

<summary><b>integration.py (Click to expand)</b></summary>

```python showLineNumbers
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig

class JiraIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = JiraPortAppConfig

```

</details>

## Guidelines for Defining Integration Configuration and Kinds

- **Provide a default configuration**: Provide a default configuration for the integration. This is to ensure that the integration is functional out of the box.
- **Add field descriptions**: Add field descriptions to the configuration fields to help users understand what they are configuring.
- **Single file**: All configurations should be defined in a single file.
- **Avoid nested classes**: Avoid nested classes for the configuration classes.

:::info Source Code
You can find the source code for the integration in the [Jira integration directory on GitHub](https://github.com/port-labs/ocean/tree/main/integrations/jira)

:::

Next, we’ll learn how to **define important configurations** such as specs, blueprints and mapping configurations to help ingest data into Port.
