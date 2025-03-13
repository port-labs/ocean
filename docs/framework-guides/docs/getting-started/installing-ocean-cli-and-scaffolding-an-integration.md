---
sidebar_position: 1
---


import CodeBlock from '@theme/CodeBlock';

# 🚀 Installing Ocean CLI and Scaffolding an Integration

In this section of the guide, you'll discover how to **install** the Ocean CLI and **scaffold** a new integration

## Requirements
Ensure Python 3.12 is installed on your computer, as mentioned in the previous section. If it's not yet installed, you can download it from the [official Python website](https://www.python.org/downloads/).

## Setting up the environment
Integrations for Port are developed using the Ocean framework. The Ocean framework provides a set of tools and libraries to help you develop, test, and deploy integrations to Port. In addition, integrations are usually developed within the [Ocean monorepo](https://github.com/port-labs/ocean/), which provides a set of automations on GitHub CI environment including testing, linting, and a Docker image build.

Developing an integration within the Ocean monorepo has some advantages:
- Contributing an integration to the Port catalog requires it to be developed within the Ocean monorepo. Hence, if you plan to contribute to Port's Ocean integration catalog, you should develop it within the Ocean monorepo.

- The Ocean monorepo provides a set of automations on GitHub CI environment including testing, linting, and building the integration Docker image. This ensures that your integration is well-tested and ready for deployment.

### Cloning the Ocean Monorepo
To develop an integration, you need to fork the [Port Ocean monorepo](https://github.com/port-labs/ocean), clone it to your local machine, and install the dependencies from the root directory.


<details>
<summary><b>Installing dependencies on Ocean monorepo (Click to expand)</b></summary>

```console showLineNumbers title="bash"
$ make install
```

</details>

### Scaffolding the project with `make new`
Next, you will scaffold the Jira integration for ingesting Projects and Issues. Run the following command to scaffold a new integration:

<details>
<summary><b>Scaffolding an integration within Ocean monorepo (Click to expand)</b></summary>

```console showLineNumbers title="bash"
$ make new
=====================================================================================
          ::::::::       ::::::::       ::::::::::           :::        ::::    :::
        :+:    :+:     :+:    :+:      :+:                :+: :+:      :+:+:   :+:
       +:+    +:+     +:+             +:+               +:+   +:+     :+:+:+  +:+
      +#+    +:+     +#+             +#++:++#         +#++:++#++:    +#+ +:+ +#+
     +#+    +#+     +#+             +#+              +#+     +#+    +#+  +#+#+#
    #+#    #+#     #+#    #+#      #+#              #+#     #+#    #+#   #+#+#
    ########       ########       ##########       ###     ###    ###    ####
=====================================================================================
By: Port.io
🚢 Unloading cargo... Setting up your integration at the dock.
  [1/10] integration_name (Name of the integration): jira
  [2/10] integration_slug (jira): jira
  [3/10] integration_short_description (A short description of the project): Integration to bring information from Jira into Port
  [4/10] full_name (Your name): Mlarmlor Dugson
  [5/10] email (Your address email <you@example.com>): mlarmlor.dugson@organization.com
  [6/10] release_date (2025-02-11):
  [7/10] is_private_integration [y/n] (n): n
  [8/10] port_client_id (you can find it using:
https://docs.getport.io/build-your-software-catalog/custom-integration/api/#find-your-port-credentials): <your-port-client-id>
  [9/10] port_client_secret (you can find it using:
https://docs.getport.io/build-your-software-catalog/custom-integration/api/#find-your-port-credentials): <your-port-client-secret>
  [10/10] is_us_region [y/n] (n): n

🌊 Ahoy, Captain! Your project is ready to set sail into the vast ocean of possibilities!
Here are your next steps:

⚓️ Install necessary packages: Run cd ./integrations/jira && make install && . .venv/bin/activate to install all required packages for your
project.
⚓️ Copy example env file: Run cp .env.example .env  and update your integration's configuration in the .env file.
⚓️ Set sail with Ocean: Run ocean sail to run the project using Ocean.
⚓️ Smooth sailing with Make: Alternatively, you can run make run ./integrations/jira to launch your project using Make.
```

</details>

With this, your newly created integration is scaffolded in the `integrations` directory of the Ocean monorepo. The integration is named `jira` and is ready for development.

## Test to see if the integration is working
To test to see that the integration is working, we will initialize the environment variables by copying the `.env.example` file to `.env` and updating the configuration in the `.env` file.

<details>

<summary><b>Setting up the environment variables (Click to expand)</b></summary>

```console showLineNumbers title="bash"
$ cd ./integrations/jira
$ cp .env.example .env
```

</details>

Next, activate the virtual environment and run the integration:

<details>

<summary><b>Running the integration (Click to expand)</b></summary>

```console showLineNumbers title="bash"
$ poetry shell
$ make run

=====================================================================================
          ::::::::       ::::::::       ::::::::::           :::        ::::    :::
        :+:    :+:     :+:    :+:      :+:                :+: :+:      :+:+:   :+:
       +:+    +:+     +:+             +:+               +:+   +:+     :+:+:+  +:+
      +#+    +:+     +#+             +#++:++#         +#++:++#++:    +#+ +:+ +#+
     +#+    +#+     +#+             +#+              +#+     +#+    +#+  +#+#+#
    #+#    #+#     #+#    #+#      #+#              #+#     #+#    #+#   #+#+#
    ########       ########       ##########       ###     ###    ###    ####
=====================================================================================
By: Port.io
Setting sail... ⛵️⚓️⛵️⚓️ All hands on deck! ⚓️
🌊 Ocean version: 0.21.0
🚢 Integration version: 0.1.0-beta
```

</details>

Once you see the output above, the integration is running successfully. Stop it by pressing `Ctrl + C`.

Head over to your Port dashboard, click on `"Builder"` on the top right corner. Next click on `"Data Sources"` and you should see the Jira integration you just created. Delete it by clicking on the three dots on the right side of the integration and selecting `"Delete"`. This is to ensure the integration starts on a fresh slate when you run it again.


## Integration Structure
The integration scaffold comes with the following structure which can be visualized with the `tree` command:


<details>

<summary><b>Integration structure (Click to expand)</b></summary>

```console
$ tree

jira/
├── .port        # A folder containing configurations for the integration. See below for more details
├── changelog # A directory containing automatically generated changelog files when the integration is ready to be published
├── CHANGELOG.md    # A file containing the changelog of the integration
├── CONTRIBUTING.md # A file containing the contributing guidelines for the integration
├── debug.py    # Entry point for debugging the integration
├── main.py     # Entry point for the integration. This is where resync functions to export data to Port are defined
├── Makefile    # A file containing the commands to run the integration, it is a symlink to the Makefile in the Ocean library
├── poetry.toml # Poetry configurations for the integration's virtual environment
├── pyproject.toml      # Dependency and project metadata for the integration
├── README.md       # Description of the integration
├── sonar-project.properties    # SonarQube configurations for the integration
└── tests       # A directory containing tests for the integration
    ├── __init__.py
    └── test_sample.py
```

</details>


The `.port` directory contains configurations for the integration and is documented in detail in the [Integration Spec and Default page](../develop-an-integration/integration-spec-and-default-resources.md)

With this done, we will go ahead to implement an API client for the Jira API to fetch organizations, repositories and pull requests.

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

:::info Source Code
You can find the source code for the integration in the [Jira integration directory on GitHub](https://github.com/port-labs/ocean/tree/main/integrations/jira)

:::
