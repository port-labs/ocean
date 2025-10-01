---
title: Terraform Deployment
sidebar_label: 🌍 Terraform
sidebar_position: 2
---

import IntegrationsLibraryLink from './\_integration-list-link.md';
import UIInstallation from './\_ui-installation-process.md';
import CheckInstallation from './\_check_installation.md';

# 🌍 Terraform Deployment

This guide will walk you through deploying an integration of the Ocean framework using [Terraform](https://www.terraform.io/) and your favorite cloud
provider.

<CheckInstallation/>

## Prerequisites

- [Terraform](https://www.terraform.io/downloads.html) installed
- Credentials for the cloud provider you want to use
- [Port](https://app.getport.io) organization for the the Client ID and Client Secret
- The integration's required configurations

## Deploying the integration

<UIInstallation/>

:::note Example Implementations
The Ocean repository contains example Terraform implementations demonstrating deployment patterns. These examples serve as reference implementations and learning resources.

For production deployments, we recommend using our dedicated cloud provider repositories:
- [AWS Ocean Integration](https://github.com/port-labs/terraform-ocean-integration-factory/tree/main/examples/aws_container_app)
- [GCP Ocean Integration](https://github.com/port-labs/terraform-ocean-integration-factory/tree/main/examples/azure_container_app_azure_integration)
- [Azure Ocean Integration](https://github.com/port-labs/terraform-ocean-integration-factory/tree/main/examples/gcp_cloud_run)
:::

<IntegrationsLibraryLink/>

:::info Integration Configuration
The generic configuration for integrations can be found in
the [Integration Configuration](../developing-an-integration/testing-the-integration.md#configuration-mapping) guide.
:::

:::info Event Listener
More information about the available event listener types and optional configurations can be found in
the [Event Listeners](../framework/features/event-listener.md) guide.
:::
