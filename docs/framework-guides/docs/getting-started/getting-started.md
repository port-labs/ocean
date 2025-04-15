---
title: Getting Started
---

import CodeBlock from '@theme/CodeBlock';

# ⚡️ Getting Started

In this quickstart guide, you'll learn how to **install** the Ocean CLI, **scaffold** a new integration, add your **custom logic** and **run** the new integration locally.

## Requirements

Python 3.11

## Installation

```bash showLineNumbers
$ pip install "port-ocean[cli]"
```

## Example

### Scaffold

```bash showLineNumbers
$ ocean new

🚢 Unloading cargo... Setting up your integration at the dock.
integration_name [Name of the integration]:
$ myIntegration

integration_slug [myintegration]:
$ my_integration

integration_short_description [A short description of the project]:
$ My custom integration made for Port

full_name [Your name]:
$ Monkey D. Luffy

email [Your address email <you@example.com>]:
$ straw@hat.com

release_date [2023-08-06]:
$ 2023-08-06

is_private_integration [y/n] (y):
$ n

port_client_id (you can find it using: https://docs.port.io/build-your-software-catalog/custom-integration/api/#find-your-port-credentials):
$ <your-port-client-id>

port_client_secret (you can find it using: https://docs.port.io/build-your-software-catalog/custom-integration/api/#find-your-port-credentials):
$ <your-port-client-secret>

is_us_region [y/n] (n):
$ y

🌊 Ahoy, Captain! Your project is ready to set sail into the vast ocean of possibilities!
Here are your next steps:

⚓️ Install necessary packages: Run cd ./my_integration && make install && . .venv/bin/activate to install all required packages for your project.
⚓️ Copy example env file: Run cp .env.example .env  and update your integration's configuration in the .env file.
⚓️ Set sail with Ocean: Run ocean sail to run the project using Ocean.
⚓️ Smooth sailing with Make: Alternatively, you can run make run ./my_integration to launch your project using Make.
```

<br/>

<details>
<summary>Scaffolding the project with <code>make new</code></summary>

If you clone the [Port Ocean](https://github.com/port-labs/port-ocean) repository to your local machine, you can also use the `make new` command instead of `ocean new` to scaffold a new integration project in the integrations folder.

The make command will use the ocean new command behind the scenes.

</details>

### Develop

- Edit the file `./my_integration/main.py` to add your integration logic.

```python showLineNumbers
from typing import Any

from port_ocean.context.ocean import ocean


@ocean.on_resync('project')
async def resync_project(kind: str) -> list[dict[Any, Any]]:
    # 1. Get all projects from the source system
    # 2. Return a list of dictionaries with the raw data of the state
    return [{"some_project_key": "someProjectValue", ...}]


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    print("Starting integration")

```

- Edit the file `./my_integration/.port/spec.yaml` to add your [integration specification](../develop-an-integration/integration-spec-and-default-resources.md#specyaml-file).

```yaml showLineNumbers
# The integration name
type: my-jira-integration
description: myIntegration integration for Port Ocean
# The integration icon taken from the icon list in Port
icon: Cookiecutter
features:
  - type: exporter
    # Where in the ingest modal should this integration be shown
    section: Ticket management
    resources:
      # The kinds that this integration can export (if known)
      - kind: <ResourceName1>
      - kind: <ResourceName2>
configurations:
  - name: myJiraToken
    required: true
    type: string
    sensitive: true
  - name: jiraUrl
    type: url
```

:::tip
The `spec.yml` file is used to provide the integration specification and also a validation layer for the inputs required by the integration. The validation layer is used to verify the provided [integration configuration](../develop-an-integration/integration-configuration.md) during the integration startup process.
:::

- Edit the file `./my_integration/config.yaml` to add the default [configuration](../develop-an-integration/integration-configuration.md) of your integration.

```yaml showLineNumbers
# This is an example configuration file for the integration service.
# Please copy this file to config.yaml file in the integration folder and edit it to your needs.

port:
  clientId: "{{ from env PORT_CLIENT_ID }}" # Can be loaded using environment variable: PORT_CLIENT_ID or OCEAN__PORT__CLIENT_ID
  clientSecret: "{{ from env PORT_CLIENT_SECRET }}" # Can be loaded using environment variable: PORT_CLIENT_SECRET or OCEAN__PORT__CLIENT_SECRET
# The event listener to use for the integration service.
eventListener:
  type: POLLING
integration:
  # The identifier of this integration instance.
  # Can be loaded using environment variable: INTEGRATION_IDENTIFIER or OCEAN__INTEGRATION__IDENTIFIER
  identifier: "{{ from env INTEGRATION_IDENTIFIER }}"
  # These two should match the values in the .port/spec.yaml file
  type: "My Integration type (Gitlab, Jira, etc.)"
  config:
    myJiraToken: "{{ from env MY_INTEGRATION_CONFIG }}"
    jiraUrl: "https://example.com"
```

:::tip
The `config.yaml` file is used to specify the default configuration and parameters for the integration during its deployment phase.
:::

### Run

```bash showLineNumbers
$ cd ./my_integration
$ make install

$ . .venv/bin/activate
$ (my_integration3.11) ocean sail
Setting sail... ⛵️⚓️⛵️⚓️ All hands on deck! ⚓
INFO:     Started server process [50121]
INFO:     Waiting for application startup.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

#### Interactive API docs

An integration comes built-in with a [FastAPI](https://fastapi.tiangolo.com/) server which also provides a REST interface and a Swagger webpage.

To view the routes exposed by your integration open your browser and go to [http://localhost:8000/docs](http://localhost:8000/docs). You will see the automatic interactive API documentation for the integration routes (provided by [Swagger UI](https://github.com/swagger-api/swagger-ui)):

![IntegrationScaffoldSwagger.png](../../static/img/getting-started/IntegrationScaffoldSwagger.png)

<details>
<summary>Alternative API docs</summary>

There is an alternative to the API docs (provided by [Redoc](https://github.com/Redocly/redoc))

Open your browser and go to [http://localhost:8000/redoc](http://localhost:8000/redoc). You will see the following:

![IntegrationScaffoldSwagger.png](../../static/img/getting-started/IntegrationScaffoldRedoc.png)

</details>
