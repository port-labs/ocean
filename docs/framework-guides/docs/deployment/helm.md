---
title: Helm deployment
sidebar_label: ⚓️ Helm
sidebar_position: 2
---

import IntegrationsLibraryLink from './_integration-list-link.md';
import UIInstallation from './_ui-installation-process.md';
import CheckInstallation from './_check_installation.md';

# ⚓️ Helm deployment

This guide will walk you through deploying an integration of the Ocean framework using Helm.

<CheckInstallation/>

## Prerequisites

- [Helm](https://helm.sh/docs/intro/install/) installed
- [Kubernetes](https://kubernetes.io/docs/tasks/tools/) cluster to deploy the integration to
- [Port](https://app.getport.io) organization for the the Client ID and Client Secret
- The integration required configurations

:::caution
This guide will install the Helm chart using the current Kubernetes context. Make sure you have the correct context set
before continuing.
:::

## Deploying the integration

<UIInstallation/>

### 1. Add the Ocean Helm repository

```bash
helm repo add port-labs https://port-labs.github.io/helm-charts
helm repo update
```

### 2. Install the integration

<IntegrationsLibraryLink/>

```bash
helm upgrade --install <MY_INSTALLATION_NAME> port-labs/port-ocean \
	--set port.clientId="<PORT_CLIENT_ID>"  \
	--set port.clientSecret="<PORT_CLIENT_SECRET>"  \
	--set initializePortResources=true  \
	--set integration.identifier="<THE_INTEGRATION_WANTED_IDENTIFIER>"  \
	--set integration.type="<WHICH_INTEGRATION_TO_DEPLOY>"  \
	--set integration.eventListener.type="POLLING"  \ # The wanted event listener type
	--set integration.secrets.<INTEGRATION_SPECIFIC_SECRETS>="<SECRET_VALUE>"  \
	--set integration.config.<INTEGRATION_SPECIFIC_CONFIG>="<CONFIG_VALUE>"
```

:::info Integration Configuration
The generic configuration for integrations can be found in
the [Integration Configuration](../develop-an-integration/integration-configuration.md) guide.
:::

:::info Event Listener
More information about the available event listener types and optional configurations can be found in
the [Event Listeners](../framework/features/event-listener.md) guide.
:::