# Ocean <img src="./assets/OceanSymbol.svg" alt="Ocean" width="100" height="100" align="right">

[![Lint](https://github.com/port-labs/port-ocean/actions/workflows/lint.yml/badge.svg)](https://github.com/port-labs/port-ocean/actions/workflows/lint.yml)

Ocean is a solution created by Port to tackle the difficulties encountered when merging different third-party systems with our developer portal product. This framework offers a uniform method for executing integrations, streamlining the process and enabling platform engineers to prioritize the essential features of the third-party system.

## Installation
`pip install port-ocean[cli]` or `poetry add port-ocean[cli]`



## Run Integration
1. source the integration venv 

   ```sh
   . .venv/bin/activate
   ```

2. Run

   ```sh
   ocean sail ./path/to/integration
   ```

   

## Local Development (Framework)
1. Clone the repository

2. Install dependencies:

   ```sh
   make install
   ```

   Or (For installing integrations dependencies as well)

   ```sh
   make install/all
   ```

3. source the integration venv

   ```sh
   . .venv/bin/activate
   ```

   


## Local Development (Integration)
1. Clone the repository

2. For new integration run

   ```sh
   make new
   ```

   and follow the instructions

3. Install dependencies

4. ```sh
   cd DESIRED_INTEGRATION_FOLDER && make install
   ```

5. source the integration venv

   ```sh
   . .venv/bin/activate
   ```

6. Run the integration

   ```sh
   make run
   ```

   Or

   ```sh
   ocean sail
   ```

   

# Export Architecture

![image](./assets/ExportArchitecture.svg)

## Real-Time updates Architecture
![image](./assets/RealTimeUpdatesArchitecture.svg)

## Folder Structure
The Integration Framework follows a specific folder structure within the mono repository. This structure ensures proper organization and easy identification of integration modules. The suggested folder structure is as follows:

```
port-ocean/
├── port_ocean (framework)/
│ ├── ocean.py
│ ├── core/
| └── ...
└── integrations/
│  ├───integration_name/
│  ├──── main.py
│  ├──── pyproject.toml
│  └──── Dockerfile
├── ...
└── ...
```

- The `framework` folder contains the core logic for managing the integration lifecycle.
- Each integration is represented by a separate folder inside the `integrations` directory.
- Inside each integration folder, you'll find a `main.py` file that implements the core functionality of the integration for the specific third-party system.
- The `pyproject.toml` file inside each integration folder lists the required dependencies for that integration.

## Integration Lifecycle

![image](./assets/LifecycleOfIntegration.svg)

## Configuration
The Integration Framework utilizes a `config.yaml` file for its configuration. This file defines both the framework configuration and the integration configuration within it. Each integration is identified by its type and unique identifier, which are utilized during initialization to appropriately update Port.

Example `config.yaml`:
```yaml
# This is an example configuration file for the integration service.
# Please copy this file to config.yaml file in the integration folder and edit it to your needs.

port:
  clientId: PORT_CLIENT_ID # Can be loaded via environment variable: PORT_CLIENT_ID
  clientSecret: PORT_CLIENT_SECRET # Can be loaded via environment variable: PORT_CLIENT_SECRET
  baseUrl: https://api.getport.io/v1
# The trigger channel to use for the integration service.
triggerChannel:
  type: KAFKA / WEBHOOK
integration:
  # The name of the integration.
  identifier: "my_integration"
  # The type of the integration.
  type: "PagerDuty"
  config:
    my_git_token: "random"
    some_other_integration_config: "Very important information"
```

## Contributing
We welcome contributions to the Integration Framework project. If you have any suggestions, bug reports, or would like to contribute new features, please follow our guidelines outlined in the `CONTRIBUTING.md` file.

## License
The Integration Framework is open-source software licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0). See the `LICENSE` file for more details.

## Contact
For any questions or inquiries, please reach out to our team at support@getport.io