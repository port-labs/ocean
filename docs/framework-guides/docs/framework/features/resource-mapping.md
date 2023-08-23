---
title: Resource Mapping
sidebar_label: 🗺 Resource Mapping
sidebar_position: 1
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# 🗺 Resource Mapping

Resource Mapping is a way to map the 3rd party application entities into Port entities. Ocean is getting the Resource
Mapping
stored on the integration in the Port API.

The Resource Mapping is a YAML that tells the Ocean framework how to transform data from the integration into Port
entities.

:::danger
The Resource Mapping is being held in the integration user integration and any field inside of it can be changed by him.

The integration should not rely on the Resource Mapping specific value and should always handle the data accordingly.
:::

:::tip Setting a Default
The integration can specify a default Resource Mapping that will be set to the integration upon integration installation
by specify a default in the `.port` folder as specified in
the [Integration Spec and Defaults](../../develop-an-integration/integration-spec-and-default-resources.md#port-app-configyml-file)
page.
:::

## Structure

## Ingesting Git objects

Port's Ocean integrations allows you to ingest a variety of objects resources provided by the 3rd party API. The Ocean
integration allows you to perform extract, transform, load (ETL) on data from the GitHub API into the desired software
catalog data model.

The Ocean framework uses a YAML configuration to describe the ETL process to load data into the developer portal. The
approach reflects a golden middle between an overly opinionated 3rd part application visualization that might not work
for everyone and a too-broad approach that could introduce unneeded complexity into the developer portal.

:::note
The following structure is a generic structure that should match all integrations. The integration can extend this
structure by adding more fields to the Resource Mapping that will be used by the integration to extract more specific
data from the 3rd party application.
:::

```yaml
deleteDependentEntities: bool
createMissingRelatedEntities: bool
resources:
  - kind: str
    selector:
      query: str
    port:
      entity:
        # required
        identifier: str
        blueprint: str
        # optional
        title: str
        properties:
          MY_PROPERTY_IDENTIFIER: str
        relations:
          MY_RELATION_IDENTIFIER: str
```

The integrations makes use of the [JQ JSON processor](https://stedolan.github.io/jq/manual/) to select, modify,
concatenate, transform and perform other operations on existing fields and values from 3rd party API.

The Resource Mapping is how you specify the exact resources you want to query from the 3rd party application, and also
how you specify which entities and which properties you want to fill with data from it.

### Fields

- The root key of the Resource Mapping configuration is the `resources` key:

  ```yaml showLineNumbers
  # highlight-next-line
  resources:
    - kind: myIntegrationKind
      selector:
      ...
  ```

- The `kind` key is a specifier for one of the available kinds in the integration:

  ```yaml showLineNumbers
    resources:
      # highlight-next-line
      - kind: myIntegrationKind
        selector:
        ...
  ```


- The `selector` and the `query` keys let you filter exactly which objects from the specified `kind` will be ingested to
  the software catalog:

  ```yaml showLineNumbers
  resources:
    - kind: myIntegrationKind
      # highlight-start
      selector:
        query: "true" # JQ boolean query. If evaluated to false - skip syncing the object.
      # highlight-end
      port:
  ```

  Some example use cases:

    - To sync all objects from the specified `kind`: do not specify a `selector` and `query` key;
    - To sync all objects from the specified `kind` that start with `service`, use:

      ```yaml showLineNumbers
      query: .name | startswith("service")
      ```

    - etc.

- The `port`, `entity` and the `mappings` keys open the section used to map the 3rd party application object fields to
  Port entities. To create multiple mappings of the same kind, you can add another item to the `resources` array;

  ```yaml showLineNumbers
  resources:
    - kind: myIntegrationKind
      selector:
        query: "true"
      # highlight-start
      port:
        entity:
          mappings: # Mappings between one of the 3rd party application objects to a Port entity. Each value is a JQ query.
            identifier: ".name"
            title: ".name"
            blueprint: '"microservice"'
            properties:
              url: ".html_url"
              description: ".description"
      # highlight-end
    - kind: repository # In this instance repository is mapped again with a different filter
      selector:
        query: '.name == "MyRepositoryName"'
      port:
        entity:
          mappings: ...
  ```

  :::tip
  Pay attention to the value of the `blueprint` key, if you want to use a hardcoded string, you need to encapsulate it
  in 2 sets of quotes, for example use a pair of single-quotes (`'`) and then another pair of double-quotes (`"`)
  :::

#### Advanced Fields

The ocean framework supports additional flags to provide additional configuration, making it easier to configure its
behavior to your liking.

To use the advanced configuration and additional flags, add them as a root key to
your [Resource Mapping](#-resource-mapping), for example to add the
`createMissingRelatedEntities` flag:

```yaml showLineNumbers
# highlight-next-line
createMissingRelatedEntities: true
resources:
  ...
```

The following advanced configuration parameters are available and can be added to
the [Resource Mapping](#-resource-mapping):

<Tabs groupId="config" queryString="parameter">

<TabItem label="Delete dependent entities" value="deleteDependent">

The `delete_dependents` query parameter is used to enable the deletion of dependent Port entities. This is useful when
you have two blueprints with a required relation, and the target entity in the relation should be deleted. In this
scenario, the delete operation will fail if this flag is set to `false`, if the flag is set to `true`, the source entity
will be deleted as well.

- Default: `false` (disabled)
- Use case: Deletion of dependent Port entities. Must be enabled, if you want to delete a target entity (and its source
  entities) in a required relation.

</TabItem>

<TabItem value="createMissingRelatedEntities" label="Create missing related entities">

The `createMissingRelatedEntities` parameter is used to enable the creation of missing related Port entities
automatically in cases where the target related entity does not exist in the software catalog yet.

- Default value: `false` (do not create missing related entities)
- Use case: use `true` if you want GitHub app to create barebones related entities, in case those related entities do
  not exist in the software catalog.

</TabItem>

</Tabs>

| Field                                  | Type  | Default | Description                                                                                            |
|----------------------------------------|-------|---------|--------------------------------------------------------------------------------------------------------|
| `deleteDependentEntities`              | bool  | `false` | Delete dependent entities when the parent entity is deleted.                                           |
| `createMissingRelatedEntities`         | bool  | `false` | Create missing related entities when the parent entity is created.                                     |
| `resources`                            | array | `[]`    | A list of resources to map.                                                                            |
| `resources.[].kind`*                   | str   |         | The kind name of the resource. (Should match one of the available kinds in the integration)            |
| `resources.[].selector.query`*         | str   |         | A JQ expression that will be used to select the raw data from the 3rd party application.               |
| `resources.[].port.entity.identifier`* | str   |         | A JQ expression that will be used to extract the entity identifier.                                    |
| `resources.[].port.entity.blueprint`*  | str   |         | A JQ expression that will be used to extract the entity blueprint.                                     |
| `resources.[].port.entity.title`       | str   |         | A JQ expression that will be used to extract the entity title.                                         |
| `resources.[].port.entity.properties`  | dict  | `{}`    | An object of property identifier to JQ expressions that will be used to extract the entity properties. |
| `resources.[].port.entity.relations`   | dict  | `{}`    | An object of relation identifier to JQ expressions that will be used to extract the entity properties. |

## Specify Custom Resource Mapping Fields

The integration can specify custom fields in the Resource Mapping that will be used to validate and parse the Resource
Mapping from Port API.

Specifying custom fields is done by overriding the `CONFIG_CLASS` Property for the integration PortAppConfig handler.

### Overriding the `CONFIG_CLASS` Property

The integration can override the `CONFIG_CLASS` Property to specify a custom class that will be used to parse the
Resource Mapping. To override the `CONFIG_CLASS` Property, the integration should have a `integration.py` file in the
root of the integration folder that contains the following:

:::note
Ocean utilizes [Pydantic](https://docs.pydantic.dev/latest/) to validate and parse the Resource Mapping. The integration
can override those models by adding more fields to the model.
:::

```python
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.models import PortAppConfig, ResourceConfig, Selector
from pydantic import Field


class CustomResourceConfig(ResourceConfig):
    class CustomSelector(Selector):
        my_custom_selector_field: str = Field(alias="myCustomSelectorField")


class MyIntegrationCustomPortAppConfig(PortAppConfig):
    resources: ResourceConfig = []


class MyIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = MyIntegrationCustomPortAppConfig
```

This custom Resource Mapping will expect portAppConfig with the following format:

```yaml
deleteDependentEntities: bool
createMissingRelatedEntities: bool
resources:
  - kind: str
    selector:
      query: str
      # highlight-next-line
      myCustomSelectorField: str
    port:
      entity:
        # required
        identifier: str
        blueprint: str
        # optional
        title: str
        properties:
          MY_PROPERTY_IDENTIFIER: str
        relations:
          MY_RELATION_IDENTIFIER: str
```