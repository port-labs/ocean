---
title: Integration Spec and Defaults
sidebar_label: 📋 Integration Spec and Defaults
sidebar_position: 2
---

# 📋 Integration Spec and Defaults

This section explains the structure of the `.port` folder and its different components.

The `.port` folder is used to provide resources that are used by the Ocean framework when starting up an integration, the folder includes files that are used both in the initial startup of the integration, as well as validate its configuration in every subsequent run.

## `.port` folder

Here is an example structure for the `.port` folder:

```text
└── my_new_integration/
    ├── .port/
    │   ├── spec.yml
    │   └── resources/
    │       ├── port-app-config.yml
    │       └── blueprints.json
    └── ...
```

Let's go over the different files, their structure and functionality:

## `spec.yaml` file

The `spec.yml` file is used to provide the integration specification and also a validation layer for the inputs required by the integration. The validation layer is used to verify the provided [integration configuration](./integration-configuration.md) during the integration startup process.

### Structure

Here is the structure of a sample `spec.yml` file:

```yaml showLineNumbers
type: myIntegration
description: My integration for Port Ocean
icon: myIntegration
features:
  - type: exporter
    section: Project management
    resources:
      - kind: my_integ_kind1
      - kind: my_integ_kind2
configurations:
  - name: appHost
    required: false
    type: url
    description: "The host of the Port Ocean app. Used to set up the integration endpoint as the target for Webhooks created in the 3rd party service"
  - name: secretToken
    required: true
    type: string
    description: "The token to authenticate with the 3rd party service"
    sensitive: true
```

Let's go over the different sections and their allowed values:

#### Integration base specification

```yaml showLineNumbers
type: myIntegration
description: My integration for Port Ocean
icon: myIntegration
```

This section is used to specify the basic information of the integration, this information is used for proper display in Port's UI interface.

The integration's base spec includes:

- `type` - integration type, also determines the name of the generated image for the integration
- `description` - the description that will be displayed in Port's UI for the integration
- `icon` - the icon that will displayed in Port's UI for the integration, the value has to match one of the icons available in Port's library

#### `features` - integration feature specification

```yaml showLineNumbers
---
features:
  - type: exporter
    section: Project management
    resources:
      - kind: my_integ_kind1
      - kind: my_integ_kind2
```

This section is used to specify the features supported by the integration, this information is used for proper display in Port's UI interface.

The integration's `features` spec is an array where each item includes:

- `type` - the type of the integration
  - Available values: `exporter`/`gitops`
- `section` - the category of the integration within its type
  - Available values: `GitOps`, `Git Providers`, `Project management` and more
- `resources` - an array of key-value pairs that specify the kinds provided by the integration
  - For example - the Jira Ocean integration provides the kinds `issue` and `project`

#### `configurations` - integration configuration validation

```yaml showLineNumbers
configurations:
  - name: appHost
    required: false
    type: url
    description: "The host of the Port Ocean app. Used to set up the integration endpoint as the target for Webhooks created in the 3rd party service"
  - name: secretToken
    required: true
    type: string
    description: "The token to authenticate with the 3rd party service"
    sensitive: true
```

This section is used to specify the inputs required by the integration, this information is used to verify the [integration configuration](./integration-configuration.md) is valid before the integration starts. This information is also used to auto-generate the correct deployment snippet in Port's UI for the integration.

The integration's `configurations` spec is an array where each item includes:

- `name` - the name of the integration parameter
  - Parameters should be passed in camelCase format - `appHost`, `secretToken`, `emailAddress`, etc.
- `required` - whether the parameter is required or optional
  - Available values: `true`, `false`
- `type` - the type of the parameter
  - Available values: `string`, `number`, `boolean`, `object`, `array`, `url`
- `description` - a description for the parameter and its usage in the integration
  - Please provide a description to make it easier for users who want to use your integration to understand the different required parameters
- `sensitive` - whether this parameter is secret or sensitive
  - Available values: `true`, `false`
  - Parameters marked as sensitive are stored in the secrets mechanism provided by the integration deployment scheme (K8s secret for Helm deployment, AWS Secrets Manager for deployment in AWS ECS, etc)

:::tip
To learn more about the available parameter inputs and see examples for valid configurations, check out the [configuration validation](../framework/features/configuration-validation.md) page
:::

## Default resources

The `.port/resources` directory is used to provide default resources that will be created when the integration is installed.

The following resources are supported:

### `blueprints.json` file

```json showLineNumbers
[
  {
    "identifier": "myBlueprint",
    "title": "My Blueprint",
    "icon": "Microservice",
    "schema": {
      "properties": {
        "myProp": {
          "title": "My Property",
          "type": "string"
        }
      }
    },
    "relations": {
      "relatedBlueprint": {
        "title": "Related Blueprint",
        "target": "relatedBlueprintIdentifier",
        "required": false,
        "many": false
      }
    }
  }
]
```

The `blueprints.json` file is part of the `.port/resources` directory, it is used to specify the default [blueprints](https://docs.getport.io/build-your-software-catalog/define-your-data-model/setup-blueprint/) that will be created when the integration is installed.

#### Structure

The `blueprints.json` is a JSON file which contains an array of objects that match the [blueprint objects](https://docs.getport.io/build-your-software-catalog/define-your-data-model/setup-blueprint/#blueprint-structure) from Port's API.

:::tip
The `blueprints.json` file is optional, if it is not provided, the integration will not create any blueprints when it is installed.

**However**, to make integration easier to use and onboard into Port, it is highly recommended to provide a `blueprints.json` file which users can use as a starting point and customize the data ingested from the integration into Port
:::

### `port-app-config.yml` file

```yml showLineNumbers
resources:
  - kind: myKind
    selector:
      query: "true"
    port:
      entity:
        mappings:
          identifier: .myIdentifierField
          title: .myTitleField
          blueprint: '"myTargetBlueprintIdentifier"'
          properties:
            myProp: .myPropField
```

The `port-app-config.yml` file is part of the `.port/resources` directory, it is used to specify the default integration resource mapping that will be created when the integration is installed.

:::tip
Refer to the [resource mapping](../framework/features/resource-mapping.md) feature documentation to learn more about Ocean's mapping functionality
:::

#### Structure

The `port-app-config.yml` is a YAML file which contains a root object called `resources`, this object stores an array of definitions that tell the integration how to map the different `kind`s that it supports.

:::tip
The `port-app-config.yml` file is optional, if it is not provided, the integration will create an empty mapping when it is installed.

**However**, to make integration easier to use and onboard into Port, it is highly recommended to provide a `port-app-config.yml` file which users can use as a starting point and customize the data ingested from the integration into Port
:::
