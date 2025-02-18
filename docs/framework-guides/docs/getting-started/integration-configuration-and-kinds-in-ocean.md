---
sidebar_position: 3
---

# 🏗️ Integration Configuration and Kinds in Ocean
With the API client implemented, you will notice we are exporting three types of data, namely organizations, repositories and pull requests. In Ocean, these are referred to as kinds. Kinds are a way to categorize data in Ocean. They are used to define the structure of the data that is being exported.

In addition, some of these kinds require specific configurations to be set up. For example, the organizations kind requires the user to provide a list of organizations that they want to export data from. Similarly, the repositories kind requires the user to provide the same organizations, and the type of repositories they want to export data from. Lastly, the pull requests kind requires the user to provide the same organizations, repository type, and the type of pull requests they want to export data from.

In this guide, we will learn how to configure the integration and accept user-defined configurations for the kinds.

## Integration Configuration
Create an `integration.py` file in the same directory you defined the `client.py` file. This file will contain the configuration for the integration.

Configurations are defined using Python types, backed with [Pydantic](https://docs.pydantic.dev/latest/). Pydantic is a data validation and settings management using Python type annotations. In addition, Ocean already has a default configuration that is used to define the structure of the data that is being exported. We will inherit this class and add our custom configurations.

For each of the kinds, we will define `Selector` subclasses that will hold the parameters we are passing to the kinds.

<details>

<summary><b>Selector subclasses</b></summary>

```python showLineNumbers
from port_ocean.core.handlers.port_app_config.models import Selector
from pydantic.fields import Field


class OrganizationSelector(Selector):
    organizations: list[str] = Field(
        description="List of organizations to retrieve repositories from",
        default_factory=list,
    )


class RespositorySelector(Selector):
    organizations: list[str] = Field(
        description="List of organizations to retrieve repositories from",
        default_factory=list,
    )
    type: Literal["all", "public", "private", "forks", "sources", "member"] = Field(
        description="Type of repositories to retrieve",
        default="all",
    )


class PullRequestSelector(Selector):
    organizations: list[str] = Field(
        description="List of organizations to retrieve repositories from",
        default_factory=list,
    )
    type: Literal["all", "public", "private", "forks", "sources", "member"] = Field(
        alias="repositoryType",
        description="Type of repositories to retrieve",
        default="all",
    )
    state: Literal["open", "closed", "all"] = Field(
        description="State of pull requests to retrieve",
        default="open",
    )

```

</details>

Having done this, we will define `ResourceConfig` subclasses that will associate the selectors with the kinds.


<details>

<summary><b>ResourceConfig subclasses</b></summary>

```python showLineNumbers
from typing import Literal
// highlight-next-line
from port_ocean.core.handlers.port_app_config.models import Selector, ResourceConfig
from pydantic.fields import Field


// highlight-start
class ObjectKind:
    ORGANIZATION = "organization"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull_request"
// highlight-end


# selector classes here

// highlight-start
class GitHubOranizationResourceConfig(ResourceConfig):
    selector: OrganizationSelector
    kind: Literal["organization"]


class GitHubRepositoryResourceConfig(ResourceConfig):
    selector: RespositorySelector
    kind: Literal["repository"]


class GitHubPullRequestResourceConfig(ResourceConfig):
    selector: PullRequestSelector
    kind: Literal["pull_request"]
// highlight-end

```

</details>

Finally, we will define `AppConfig` and `BaseIntegration` subclasses that will hold the resource configurations and define the total integration configuration.

<details>

<summary><b>`AppConfig` and `BaseIntegration`</b></summary>

```python showLineNumbers
from typing import Literal
// highlight-next-line
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
// highlight-next-line
from port_ocean.core.handlers.port_app_config.models import Selector, ResourceConfig, PortAppConfig
from pydantic.fields import Field
// highlight-next-line
from port_ocean.core.integrations.base import BaseIntegration


# rest of the code here

// highlight-start
class GitHubPortAppConfig(PortAppConfig):
    resources: list[
        GitHubOranizationResourceConfig
        | GitHubRepositoryResourceConfig
        | GitHubPullRequestResourceConfig
        | ResourceConfig
    ] = (
        Field(default_factory=list)
    )


class GitHubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitHubPortAppConfig

// highlight-end

```

</details>

## Conclusion
In this guide, we learned how to configure the integration and accept user-defined configurations for the kinds. We defined `Selector` subclasses that hold the parameters we are passing to the kinds, `ResourceConfig` subclasses that associate the selectors with the kinds, and `AppConfig` and `BaseIntegration` subclasses that hold the resource configurations and define the total integration configuration.

Your `integration.py` file should look like this:

<details>

<summary><b>Integration Configuration</b></summary>

```python showLineNumbers
from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field


class ObjectKind:
    ORGANIZATION = "organization"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull_request"


class OrganizationSelector(Selector):
    organizations: list[str] = Field(
        description="List of organizations to retrieve repositories from",
        default_factory=list,
    )


class RespositorySelector(Selector):
    organizations: list[str] = Field(
        description="List of organizations to retrieve repositories from",
        default_factory=list,
    )
    type: Literal["all", "public", "private", "forks", "sources", "member"] = Field(
        description="Type of repositories to retrieve",
        default="all",
    )


class PullRequestSelector(Selector):
    organizations: list[str] = Field(
        description="List of organizations to retrieve repositories from",
        default_factory=list,
    )
    type: Literal["all", "public", "private", "forks", "sources", "member"] = Field(
        alias="repositoryType",
        description="Type of repositories to retrieve data from",
        default="all",
    )
    state: Literal["open", "closed", "all"] = Field(
        description="State of pull requests to retrieve",
        default="open",
    )


class GitHubOranizationResourceConfig(ResourceConfig):
    selector: OrganizationSelector
    kind: Literal["organization"]


class GitHubRepositoryResourceConfig(ResourceConfig):
    selector: RespositorySelector
    kind: Literal["repository"]


class GitHubPullRequestResourceConfig(ResourceConfig):
    selector: PullRequestSelector
    kind: Literal["pull_request"]


class GitHubPortAppConfig(PortAppConfig):
    resources: list[
        GitHubOranizationResourceConfig
        | GitHubRepositoryResourceConfig
        | GitHubPullRequestResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class GitHubIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GitHubPortAppConfig

```

</details>


:::tip Source Code
You can find the source code for the integration in the [Developing An Integration repository on GitHub](https://github.com/port-labs/developing-an-integration)

:::

Next, we will learn how to send data to Port using the API client we implemented.
