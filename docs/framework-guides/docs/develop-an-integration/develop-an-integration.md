---
title: Introduction
sidebar_label: 🔧 Introduction
---

# 🔧 Introduction

This section builds on the [getting started](../getting-started/getting-started.md) section which shows how to install the Ocean CLI and scaffold a new integration to begin development.

This section dives deeper into the different components that make up an Ocean integration, as well as examples on how to configure and test them.

Finally, this section covers the integration publishing process.

## Ocean integration development flow

To develop and publish an integration you need to complete the following steps:

:::tip step order
These steps do not follow a specific order. Some steps only become relevant near the end of the integration's development, such as publishing.
:::

1. Scaffold a new integration, as seen in [getting started](../getting-started/installing-ocean-cli-and-scaffolding-an-integration.md)
2. Add any required code libraries and the [code and logic](./update-integration-code.md) required for the new integration
   1. Be sure to go over the integration [performance](./performance.md) and [code guidelines](./guidelines.md) to ensure a performant and well written integration
3. Update the [`.port/spec.yml`](./integration-spec-and-default-resources.md#specyaml-file) file with metadata of the integration, including the provided kinds and required parameters
4. Update the [`config.yaml`](./integration-configuration.md) file with configuration and parameters for the integration
5. (Optional) Add default definitions to the [`.port/resources`](./integration-spec-and-default-resources.md#port-folder) directory such as [default blueprints](./integration-spec-and-default-resources.md#blueprintsjson-file) and integration [mapping](./integration-spec-and-default-resources.md#port-app-configyml-file)
6. Create the necessary documentation for the new integration including the README and a changelog
7. [Publish](./publish-an-integration.md) the integration
