---
title: Helm Deployment
sidebar_label: ⚓️ Helm
sidebar_position: 1
---

import IntegrationsLibraryLink from './\_integration-list-link.md';
import UIInstallation from './\_ui-installation-process.md';
import CheckInstallation from './\_check_installation.md';

# ⚓️ Helm Deployment

This guide will walk you through deploying an integration of the Ocean framework using [Helm](https://helm.sh/).

<CheckInstallation/>

## Prerequisites

- [Helm](https://helm.sh/docs/intro/install/) installed
- [Kubernetes](https://kubernetes.io/docs/tasks/tools/) cluster to deploy the integration to
- [Port](https://app.getport.io) organization for the the Client ID and Client Secret
- The integration's required configurations

:::caution
This guide will install the Helm chart using the current Kubernetes context. Make sure you have the correct context set
before continuing.
:::

## Deploying the integration

<UIInstallation/>

### 1. Add the Ocean Helm repository

```bash showLineNumbers
helm repo add port-labs https://port-labs.github.io/helm-charts
helm repo update
```

### 2. Install the integration

<IntegrationsLibraryLink/>

```bash showLineNumbers
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

:::tip Integration Configuration
The generic configuration for integrations can be found in
the [integration configuration](../develop-an-integration/integration-configuration.md) guide.
:::

:::tip Event Listener
More information about the available event listener types and optional configurations can be found in
the [event listeners](../framework/features/event-listener.md) guide.
:::

## Advanced configruation
The Ocean framework supports [advanced configuration](../framework/advanced-configuration.md) using environment variables. The Ocean Helm chart allows setting these variables using Helm parameters. This can be done in one of two ways:

1. Using Helm's `--set` flag:
```sh showLineNumbers
helm upgrade --install <MY_INSTALLATION_NAME> port-labs/port-ocean \
  # Standard installation flags
  # ...
  --set extraEnv[0].name=HTTP_PROXY \
  --set extraEnv[0].value=http://my-proxy.com:1111
```

2. The Helm `values.yaml` file:
```yaml showLineNumbers
# The rest of the configuration
# ...
extraEnvs:
  - name: HTTP_PROXY
    value: http://my-proxy.com:1111
```