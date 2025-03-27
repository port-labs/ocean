---
title: Resource Mapping
sidebar_label: 🗺 Resource Mapping
sidebar_position: 1
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

# 🗺 Resource Mapping

Resource Mapping is an ETL layer built into the Ocean framework. Ocean integrations can use the resource mapping configuration to parse and map data from the integrated 3rd-party service to standard Port entities.

## Usage

A resource mapping is a YAML configuration that can be applied to an integration in the following ways:

- Via a [`port-app-config.yml`](../../develop-an-integration/integration-spec-and-default-resources.md#port-app-configyml-file) file that is part of the [`.port`](../../develop-an-integration/integration-spec-and-default-resources.md#port-folder) specification folder of the integration
- By updating the integration configuration through Port's UI
- By updating the integration configuration by making a PATCH request to Port's `https://api.getport.io/v1/integration/<INTEGRATION_IDENTIIFER>` route with the updated configuration

The Ocean integration uses the resource mapping to process an object received in the response from the 3rd-party service, and transform it into the desired [Port entity](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/#entity-json-structure).

:::tip
The `port-app-config.yml` file is optional, if it is not provided, the integration will create an empty resource mapping when it is installed.

However, to make integration easier to use and onboard into Port, it is highly recommended to provide a `port-app-config.yml` file which users can use as a starting point and customize the data ingested from the integration into Port
:::

:::danger
The resource mapping is customizable and can always be modified by the user who installed the integration.

As an integration developer you should not assume a specific field, value or logic exists in the resource mapping used by the user.

You can always assume that the resource mapping makes use of JQ and follows the basic field structure outlined in the [structure](#structure) section.
:::

## Structure

```yaml showLineNumbers
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

Port's Ocean integrations allows you to ingest a variety of objects resources provided by the 3rd-party API. The Ocean
integration allows you to perform extract, transform, load (ETL) on data from the 3rd-party API responses into the desired software
catalog entities and data model.

The Ocean framework uses the resource mapping to describe the ETL process to load data into the developer portal. The
approach reflects a middle-ground between an overly opinionated 3rd-party application visualization that might not work
for everyone and a too-broad approach that could introduce unneeded complexity or force developers to implement the additional mapping on their own.

:::note
The following structure is a generic structure that should match all integrations. The integration can extend this
structure by adding more fields to the resource mapping that will be used by the integration to extract more specific
data from the 3rd party application.
:::

The integrations makes use of the [JQ JSON processor](https://stedolan.github.io/jq/manual/) to select, modify,
concatenate, transform and perform other operations on existing fields and values from 3rd-party API.

The resource mapping is how you specify the exact resources you want to query from the 3rd-party application, and also
how you specify which entities and which properties you want to fill with data from it.

### Fields

- The root key of the resource mapping configuration is the `resources` key:

  ```yaml showLineNumbers
  # highlight-next-line
  resources:
    - kind: myIntegrationKind
      selector:
      ...
  ```

- The `kind` key is a specifier for one of the `kind`s provided by the integration:

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

  - To sync all objects from the specified `kind`: do not specify a `selector` and `query` key
  - To sync all objects from the specified `kind` whose `name` key starts with `service`, use:

    ```yaml showLineNumbers
    query: .name | startswith("service")
    ```

- The `port`, `entity` and the `mappings` keys open the section used to map the 3rd-party application object fields to
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
    - kind: myIntegrationKind # In this instance myIntegrationKind is mapped again with a different filter
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
- The `itemsToParse` key makes it possible to create multiple entities from a single array attribute of a 3rd-party application object.
In order to reference an array item attribute, use the `.item` JQ expression prefix.
Here is an example mapping configuration that uses the `itemsToParse` syntax with an `issue` kind provided an Ocean Jira integration:
```yaml
  - kind: issue
    selector:
      query: .item.name != 'test-item' and .issueType == 'Bug' 
    port:
      itemsToParse: .fields.comments
      entity:
        mappings:
          identifier: .item.id
          blueprint: '"comment"'
          properties:
            text: .item.text
          relations:
             issue: .key
```
Here is a sample JSON object (3rd-party response) that the mapping will be used for:

```json
{
  "url": "https://example.com/issue/1",
  "status": "Open",
  "issueType": "Bug",
  "comments": [
    {
      "id": "123",
      "text": "This issue is not reproducing"
    },
    {
      "id": "456",
      "text": "Great issue!"
    }
  ],
  "assignee": "user1",
  "reporter": "user2",
  "creator": "user3",
  "priority": "High",
  "created": "2024-03-18T10:00:00Z",
  "updated": "2024-03-18T12:30:00Z",
  "key": "ISSUE-1"
}
```

The result of the mapping will be multiple `comment` entities, based on the items from the `comments` array in the JSON.
#### Advanced Fields

The Ocean framework supports additional flags to provide additional configuration, making it easier to configure its
behavior to your liking.

To use the advanced configuration and additional flags, add them as a root key to
your resource mapping, for example to add the `createMissingRelatedEntities` flag:

```yaml showLineNumbers
# highlight-next-line
createMissingRelatedEntities: true
resources: ...
```

The following advanced configuration parameters are available and can be added to
the resource mapping:

<Tabs groupId="config" queryString>

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
- Use case: use `true` if you want Ocean integration to create barebones related entities, in case those related entities do
  not already exist in the software catalog.

</TabItem>

</Tabs>

### Complete resource mapping fields reference

The following table specifies all of the fields that can be specified in the resource mapping configuration:

| Field                                   | Type  | Default | Description                                                                                                                                                                                                                     |
|-----------------------------------------| ----- | ------- |---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `deleteDependentEntities`               | bool  | `false` | Delete dependent entities when the parent entity is deleted.                                                                                                                                                                    |
| `createMissingRelatedEntities`          | bool  | `false` | Create missing related entities when the child entity is created.                                                                                                                                                               |
| `resources`                             | array | `[]`    | A list of resources to map.                                                                                                                                                                                                     |
| `resources.[].kind`\*                   | str   |         | The kind name of the resource. (Should match one of the available kinds in the [integration specification](../../develop-an-integration/integration-spec-and-default-resources.md#features---integration-feature-specification)) |
| `resources.[].selector.query`\*         | str   |         | A JQ expression that will be used to filter the raw data from the 3rd-party application.                                                                                                                                        |
| `resources.[].port.itemsToParse`        | str   |         | A JQ expression that will be used to apply the mapping on the items of an array and generate multiple entities from the array items.                                                                                              |
| `resources.[].port.entity.identifier`\* | str   |         | A JQ expression that will be used to extract the entity identifier.                                                                                                                                                             |
| `resources.[].port.entity.blueprint`\*  | str   |         | A JQ expression that will be used to extract the entity blueprint.                                                                                                                                                              |
| `resources.[].port.entity.title`        | str   |         | A JQ expression that will be used to extract the entity title.                                                                                                                                                                  |
| `resources.[].port.entity.properties`   | dict  | `{}`    | An object of property identifier to JQ expressions that will be used to extract the entity properties.                                                                                                                          |
| `resources.[].port.entity.relations`    | dict  | `{}`    | An object of relation identifier to JQ expressions that will be used to extract the entity properties.                                                                                                                          |

## Specify custom resource mapping fields

The integration can support custom fields in the resource mapping that can be used to extend the functionality provided by the resource mapping.

Specifying custom fields is done by overriding the `CONFIG_CLASS` property for the integration `PortAppConfig` handler.

### Overriding the `CONFIG_CLASS` property

The integration can override the `CONFIG_CLASS` property to specify a custom class that will be used to parse the
resource mapping. To override the `CONFIG_CLASS` property, the integration should have an `integration.py` file in the
root of the integration folder that contains the following:

```python showLineNumbers
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.models import PortAppConfig, ResourceConfig, Selector
from pydantic import Field


class CustomResourceConfig(ResourceConfig):
    # The following class inherits the base "selector" key in the PortAppConfig and extends it
    class CustomSelector(Selector):
        # Every field specified here will be added to the fields available in the "selector" key
        my_custom_selector_field: str = Field(alias="myCustomSelectorField")

# The following class inherits the base PortAppConfig and can extend the types it expects for its different fields
class MyIntegrationCustomPortAppConfig(PortAppConfig):
    # every type assignment made inside the class will modify the base types used when parsing the PortAppConfig
    resources: ResourceConfig = []


class MyIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = MyIntegrationCustomPortAppConfig
```

:::note
Ocean utilizes [Pydantic](https://docs.pydantic.dev/latest/) to validate and parse the resource mapping. The integration
can override those models by adding more fields to the model.
:::

This custom `CONFIG_CLASS` will expect resource mappings with the following format:

```yaml showLineNumbers
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
