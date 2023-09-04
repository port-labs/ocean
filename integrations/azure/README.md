# Azure

Integration to import azure resources into Port.

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean
- azure-mgmt-resource
- azure-identity
- requests
- aiohttp
- cloudevents


## Pre-Requisites

Before using this module, make sure you have completed the following prerequisites:
- Install the [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) and login to your Azure account.
    ```bash
    az login
    ```
- Export your [Port Credentials](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/api/#find-your-port-credentials).

### Azure

Before deploying the integration you'll need to consider and check the following prerequisites:

#### Azure Authorization
The integration will need to have permissions to read the resources you want to import from Azure to Port.

- **Azure Role Definition**: Permissions are granted to the integration using an Azure Role Definition. The integration will create a new Role Definition with the required permissions.
  - **Permissions** - The integration will need to have the following permissions: (An example will be provided later on in the documentation)
    - **Actions**: You'll need to specify the [actions](https://learn.microsoft.com/en-us/azure/role-based-access-control/role-definitions#actions) you want to grant the integration.

#### Azure Infrastructure

- **Azure Subscription**: You'll need an Azure subscription to deploy the integration.
- **Azure Resource Group**: The integration need to be deployed to an Azure Resource Group, you can pass an existing one, or the integration will create a new one. (To override add `resource_group_id=<your-resource-group-id>`)
- **Azure Container App**: The integration will be deployed using Azure Container App. Which requires some extra infrastructure to be deployed, by default if not specified otherwise we will deploy the required infrastructure.
  - **Azure Log Analytics Workspace**: The integration will create a new Log Analytics Workspace to store the logs of the integration.
  - **Azure Container App Environment**: The integration will create a new Container App Environment to deploy the integration to.

#### Azure Event Grid
- **Azure Event Grid System Topic**: To allow the integration to receive events from Azure, an Event Grid System Topic of type `Microsoft.Resources.Subscriptions` will be needed. The integration will create a new System Topic and will subscribe to it. (Due to a limitation in Azure only one Event Grid System Topic of type `Microsoft.Resources.Subscriptions` can be created per subscription, so if you already have one you'll need to pass it to the integration using `event_grid_system_topic_name=<your-event-grid-system-topic-name>`) Further example on how to create the System Topic will be provided later on in the documentation.
- **Azure Event Grid Subscription**: To Pass the events from the System Topic to the integration, an Event Grid Subscription will be needed. The integration will create a new Subscription and will pass the events to the integration.


## Installation

The integration is deployed using Terraform on Azure [ContainerApp](https://learn.microsoft.com/en-us/azure/container-apps/overview).

The integration can be triggered in two ways:
- On events sent from the Azure Event Grid.
- When a change in the integration configuration is detected.

To deploy the integration, do the following:

Save the following code in a file named `main.tf`:

```hcl
module "ocean_container_app_example_azure-integration" {
  source  = "port-labs/integration-factory/ocean//examples/azure_container_app_azure_integration"
  version = ">=0.0.7"
  
  port_client_id = "xxxxx-xxxx-xxxx-xxxx"
  port_client_secret = "yyyy-yyyy-yyyy-yyyy"
}
```
    
Then run the following commands:

```sh
terraform init
terraform apply
```

## Supported Kinds


### Resource Group

The mapping should refer to one of the resource groups from the example response: [Azure documentation](https://docs.microsoft.com/en-us/rest/api/resources/resourcegroups/list)

<details>
<summary>blueprints.json</summary>

```json
  {
    "identifier": "resourceGroup",
    "description": "This blueprint represents an Azure Resource Group in our software catalog",
    "title": "Resource Group",
    "icon": "Azure",
    "schema": {
      "properties": {
        "location": {
          "title": "Location",
          "type": "string"
        },
        "provisioningState": {
          "title": "Provisioning State",
          "type": "string"
        },
        "tags": {
          "title": "Tags",
          "type": "object"
        }
      }
    }
  }
```
</details>


<details>
<summary>port-app-config.yaml</summary>

```yaml
  - kind: Microsoft.Resources/resourceGroups
    selector:
      query: "true"
      # azure resource api version to query
      apiVersion: '2022-09-01'
    port:
      entity:
        mappings:
          # lower case the resource group namespace and name to align with other azure resources
          identifier: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | join("/")'
          title: .name
          blueprint: '"resourceGroup"'
          properties:
            location: .location
            # the provisioning state property is returned in lower case when using the SDK and in camelCase when using the REST API
            # therefore supporting both (for users who use the SDK)
            provisioningState: .properties.provisioningState + .properties.provisioning_state
            tags: .tags
```

</details>

### Container App

The mapping should refer to one of the container apps from the example response: [Azure documentation](https://docs.microsoft.com/en-us/rest/api/container-apps/containerapps/list)

<details>
<summary>blueprints.json</summary>

```json
  {
    "identifier": "containerApp",
    "description": "This blueprint represents an Azure Container App in our software catalog",
    "title": "Container App",
    "icon": "Azure",
    "schema": {
      "properties": {
        "location": {
          "title": "Location",
          "type": "string"
        },
        "provisioningState": {
          "title": "Provisioning State",
          "type": "string",
          "enum": [
            "Canceled",
            "InProgress",
            "Succeeded",
            "Deleting",
            "Failed"
          ]
        },
        "outboundIpAddresses": {
          "title": "Outbound IP Addresses",
          "type": "array"
        },
        "externalIngress": {
          "title": "External Ingress",
          "type": "boolean"
        },
        "hostName": {
          "title": "Host Name",
          "type": "string"
        },
        "minReplicas": {
          "title": "Min Replicas",
          "type": "number"
        },
        "maxReplicas": {
          "title": "Max Replicas",
          "type": "number"
        }
      },
      "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
      "resourceGroup": {
        "target": "resourceGroup",
        "title": "Resource Group",
        "required": false,
        "many": false
      }
    }
  }
```

</details>

<details>
<summary>port-app-config.yaml</summary>

```yaml
  - kind: Microsoft.App/containerApps
    selector:
      query: "true"
      # azure resource api version to query
      apiVersion: '2022-03-01'
    port:
      entity:
        mappings:
          # lower case the resource group namespace and name to align with other azure resources
          identifier: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | join("/")'
          title: .name
          blueprint: '"containerApp"'
          properties:
            location: .location
            provisioningState: .properties.provisioningState
            outboundIpAddresses: .properties.outboundIpAddresses
            externalIngress: .properties.configuration.ingress.external
            hostName: .properties.configuration.ingress.fqdn
            minReplicas: .properties.template.scale.minReplicas
            maxReplicas: .properties.template.scale.maxReplicas
          relations:
            # lower case the resource group namespace and name to align with other azure resources
            resourceGroup: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | .[:5] |join("/")'
```
</details>

### AKS

The mapping should refer to one of the AKS from the example response: [Azure documentation](https://docs.microsoft.com/en-us/rest/api/aks/managedclusters/list)

<details>
<summary>blueprints.json</summary>

```json
  {
    "identifier": "aks",
    "description": "This blueprint represents an Azure Kubernetes Service in our software catalog",
    "title": "AKS",
    "icon": "Azure",
    "schema": {
      "properties": {
        "location": {
          "title": "Location",
          "type": "string"
        },
        "provisioningState": {
          "title": "Provisioning State",
          "type": "string"
        },
        "powerState": {
          "title": "Power State",
          "type": "string"
        },
        "kubernetesVersion": {
          "title": "Kubernetes Version",
          "type": "string"
        },
        "currentKubernetesVersion": {
          "title": "Current Kubernetes Version",
          "type": "string"
        },
        "dnsPrefix": {
          "title": "DNS Prefix",
          "type": "string"
        },
        "fqdn": {
          "title": "FQDN",
          "type": "string"
        },
        "nodeResourceGroup": {
          "title": "Node Resource Group",
          "type": "string"
        },
        "enableRBAC": {
          "title": "Enable RBAC",
          "type": "boolean"
        },
        "supportPlan": {
          "title": "Support Plan",
          "type": "string"
        },
        "networkPlugin": {
          "title": "Network Plugin",
          "type": "string"
        },
        "podCIDR": {
          "title": "Pod CIDR",
          "type": "string"
        },
        "serviceCIDR": {
          "title": "Service CIDR",
          "type": "string"
        },
        "dnsServiceIp": {
          "title": "DNS Service IP",
          "type": "string"
        },
        "outboundType": {
          "title": "Outbound Type",
          "type": "string"
        },
        "loadBalancerSKU": {
          "title": "Load Balancer SKU",
          "type": "string"
        },
        "maxAgentPools": {
          "title": "Max Agent Pools",
          "type": "number"
        },
        "skuTier": {
          "title": "Tier",
          "type": "string",
          "enum": [
            "Free",
            "Paid",
            "Standard"
          ]
        }
      },
      "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
      "resourceGroup": {
        "target": "resourceGroup",
        "title": "Resource Group",
        "required": false,
        "many": false
      }
    }
  }
```

</details>

<details>
<summary>port-app-config.yaml</summary>

```yaml
    port:
      entity:
        mappings:
          # lower case the resource group namespace and name to align with other azure resources
          identifier: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | join("/")'
          title: .name
          blueprint: '"aks"'
          properties:
            location: .location
            provisioningState: .properties.provisioningState
            powerState: .properties.powerState.code
            kubernetesVersion: .properties.kubernetesVersion
            currentKubernetesVersion: .properties.currentKubernetesVersion
            dnsPrefix: .properties.dnsPrefix
            fqdn: .properties.fqdn
            nodeResourceGroup: .properties.nodeResourceGroup
            enableRBAC: .properties.enableRBAC
            supportPlan: .properties.supportPlan
            networkPlugin: .properties.networkProfile.networkPlugin
            podCIDR: .properties.networkProfile.podCidr
            serviceCIDR: .properties.networkProfile.serviceCidr
            dnsServiceIp: .properties.networkProfile.dnsServiceIP
            outboundType: .properties.networkProfile.outboundType
            loadBalancerSKU: .properties.networkProfile.loadBalancerSku
            maxAgentPools: .properties.maxAgentPools
            skuTier: .properties.sku.tier
          relations:
            # lower case the resource group namespace and name to align with other azure resources
            resourceGroup: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | .[:5] |join("/")'
```

</details>

### Load Balancer

The mapping should refer to one of the load balancers from the example response: [Azure documentation](https://docs.microsoft.com/en-us/rest/api/network/loadbalancers/list)

<details>
<summary>blueprints.json</summary>

```json
  {
    "identifier": "loadBalancer",
    "description": "This blueprint represents an Azure Load Balancer in our software catalog",
    "title": "Load Balancer",
    "icon": "Azure",
    "schema": {
      "properties": {
        "location": {
          "title": "Location",
          "type": "string"
        },
        "tags": {
          "title": "Tags",
          "type": "object"
        },
        "provisioningState": {
          "title": "Provisioning State",
          "type": "string",
          "enum": [
              "Succeeded",
              "Updating",
              "Deleting",
              "Failed"
          ]
        },
        "frontendIpResourceIds": {
            "title": "Frontend IP Resource IDs",
            "type": "array"
        },
        "backendAddressPoolsResourceIds": {
            "title": "Backend Address Pools Resource IDs",
            "type": "array"
        },
        "loadBalancingRulesResourceIds": {
            "title": "Load Balancing Rules Resource IDs",
            "type": "array"
        },
        "probesResourceIds": {
            "title": "Probes Resource IDs",
            "type": "array"
        },
        "inboundNatRulesResourceIds": {
            "title": "Inbound NAT Rules Resource IDs",
            "type": "array"
        },
        "inboundNatPoolsResourceIds": {
            "title": "Inbound NAT Pools Resource IDs",
            "type": "array"
        }
      },
      "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
      "resourceGroup": {
        "target": "resourceGroup",
        "title": "Resource Group",
        "required": false,
        "many": false
      }
    }
  }
```

</details>

<details>
<summary>port-app-config.yaml</summary>

```yaml
  - kind: Microsoft.Network/loadBalancers
    selector:
        query: "true"
        # azure resource api version to query
        apiVersion: '2023-02-01'
    port:
      entity:
        mappings:
          # lower case the resource group namespace and name to align with other azure resources
          identifier: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | join("/")'
          title: .name
          blueprint: '"loadBalancer"'
          properties:
            location: .location
            provisioningState: .properties.provisioningState
            tags: .tags
            frontendIpResourceIds: .properties.frontendIPConfigurations[].id
            backendAddressPoolResourceIds: .properties.backendAddressPools[].id
            loadBalancingRulesResourceIds: .properties.loadBalancingRules[].id
            probesResourceIds: .properties.probes[].id
            inboundNatRulesResourceIds: .properties.inboundNatRules[].id
            inboundNatPoolsResourceIds: .properties.inboundNatPools[].id
          relations:
            # lower case the resource group namespace and name to align with other azure resources
            resourceGroup: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | .[:5] |join("/")'
```

</details>

### Virtual Machine

The mapping should refer to one of the virtual machines from the example response: [Azure documentation](https://docs.microsoft.com/en-us/rest/api/compute/virtualmachines/list)

<details>
<summary>blueprints.json</summary>

```json
  {
    "identifier": "virtualMachine",
    "description": "This blueprint represents an Azure Virtual Machine in our software catalog",
    "title": "Virtual Machine",
    "icon": "Azure",
    "schema": {
      "properties": {
        "location": {
          "title": "Location",
          "type": "string"
        },
        "provisioningState": {
          "title": "Provisioning State",
          "type": "string"
        },
        "vmSize": {
          "title": "VM Size",
          "type": "string"
        },
        "osDiskName": {
          "title": "OS Disk Name",
          "type": "string"
        },
        "osDiskType": {
          "title": "OS Disk Type",
          "type": "string"
        },
        "osDiskCaching": {
          "title": "OS Disk Caching",
          "type": "string"
        },
        "osDiskSizeGB": {
          "title": "OS Disk Size GB",
          "type": "number"
        },
        "osDiskCreateOption": {
          "title": "OS Disk Create Option",
          "type": "string"
        },
        "networkInterfaceIds": {
          "title": "Network Interface IDs",
          "type": "array"
        },
        "licenseType": {
          "title": "License Type",
          "type": "string"
        },
        "vmOsProfile": {
          "title": "VM OS Profile",
          "type": "object"
        },
        "vmHardwareProfile": {
          "title": "VM Hardware Profile",
          "type": "object"
        },
        "vmStorageProfile": {
          "title": "VM Storage Profile",
          "type": "object"
        },
        "tags": {
          "title": "Tags",
          "type": "object"
        }
      },
      "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
      "resourceGroup": {
        "target": "resourceGroup",
        "title": "Resource Group",
        "required": false,
        "many": false
      }
    }
  }
```

</details>

<details>
<summary>port-app-config.yaml</summary>

```yaml
  - kind: Microsoft.Compute/virtualMachines
    selector:
        query: "true"
        # azure resource api version to query
        apiVersion: '2023-03-01'
    port:
      entity:
        mappings:
          # lower case the resource group namespace and name to align with other azure resources
          identifier: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | join("/")'
          title: .name
          blueprint: '"virtualMachine"'
          properties:
            location: .location
            provisioningState: .properties.provisioningState
            vmSize: .properties.hardwareProfile.vmSize
            osDiskName: .properties.storageProfile.osDisk.name
            osType: .properties.storageProfile.osDisk.osType
            osDiskCaching: .properties.storageProfile.osDisk.caching
            osDiskSizeGB: .properties.storageProfile.osDisk.diskSizeGB
            osDiskCreateOption: .properties.storageProfile.osDisk.createOption
            networkInterfaceIds: .properties.networkProfile.networkInterfaces[].id
            licenseType: .properties.licenseType
            vmOsProfile: .properties.osProfile
            vmHardwareProfile: .properties.hardwareProfile
            vmStorageProfile: .properties.storageProfile
            tags: .tags
          relations:
            # lower case the resource group namespace and name to align with other azure resources
            resourceGroup: '.id | split("/") | .[3] |= ascii_downcase | .[4] |= ascii_downcase | .[:5] |join("/")'
```

</details>


### Storage Account

The mapping should refer to one of the storage accounts from the example response: [Azure documentation](https://docs.microsoft.com/en-us/rest/api/storagerp/storageaccounts/list)

<details>
<summary>blueprints.json</summary>

```json
  {
    "identifier": "storageAccount",
    "description": "This blueprint represents an Azure Storage Account in our software catalog",
    "title": "Storage Account",
    "icon": "Azure",
    "schema" : {
      "properties": {
        "location": {
          "title": "Location",
          "type": "string"
        },
        "provisioningState": {
          "title": "Provisioning State",
          "type": "string",
          "enum": [
              "Creating",
              "ResolvingDNS",
              "Succeeded"
          ]
        },
        "creationTime": {
          "title": "Creation Time",
          "type": "string",
          "format": "date-time"
        },
        "isHnsEnabled": {
          "title": "Is HNS Enabled",
          "type": "boolean",
          "default": false
        },
        "fileEncryptionEnabled": {
          "title": "File Encryption Enabled",
          "type": "boolean"
        },
        "blobEncryptionEnabled": {
          "title": "Blob Encryption Enabled",
          "type": "boolean"
        },
        "primaryLocation": {
          "title": "Primary Location",
          "type": "string"
        },
        "secondaryLocation": {
          "title": "Secondary Location",
          "type": "string"
        },
        "statusOfPrimary": {
          "title": "Status of Primary",
          "type": "string",
          "enum": [
                "available",
                "unavailable"
          ],
          "enumColors": {
            "unavailable": "red",
            "available": "green"
          }
        },
        "statusOfSecondary": {
          "title": "Status of Secondary",
          "type": "string",
          "enum": [
                "available",
                "unavailable"
          ],
          "enumColors": {
            "unavailable": "red",
            "available": "green"
          }
        },
        "tags": {
          "title": "Tags",
          "type": "object"
        },
        "allowBlobPublicAccess": {
          "title": "Allow Blob Public Access",
          "type": "boolean"
        }
      },
      "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
      "resourceGroup": {
        "target": "resourceGroup",
        "title": "Resource Group",
        "required": false,
        "many": false
      }
    }
  }
```

</details>

<details>
<summary>port-app-config.yaml</summary>

```yaml
  - kind: Microsoft.Storage/storageAccounts
    selector:
        query: "true"
        # azure resource api version to query
        apiVersion: '2023-01-01'
    port:
      entity:
        mappings:
          # lower case the resource group namespace and name to align with other azure resources
          identifier: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | join("/")'
          title: .name
          blueprint: '"storageAccount"'
          properties:
            location: .location
            provisioningState: .properties.provisioningState
            creationTime: .properties.creationTime
            isHnsEnabled: .properties.isHnsEnabled
            fileEncryptionEnabled: .properties.encryption.services.file.enabled
            blobEncryptionEnabled: .properties.encryption.services.blob.enabled
            primaryLocation: .properties.primaryLocation
            secondaryLocation: .properties.secondaryLocation
            statusOfPrimary: .properties.statusOfPrimary
            statusOfSecondary: .properties.statusOfSecondary
            allowBlobPublicAccess: .properties.allowBlobPublicAccess
            tags: .tags
          relations:
            # lower case the resource group namespace and name to align with other azure resources
            resourceGroup: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | .[:5] |join("/")'
```

</details>


### Storage Container (Blob)

The mapping should refer to one of the storage containers from the example response: [Azure documentation](https://learn.microsoft.com/en-us/rest/api/storagerp/blob-containers/list)

<details>
<summary>blueprints.json</summary>

```json
  {
    "identifier": "storageContainer",
    "description": "This blueprint represents an Azure Storage Container in our software catalog",
    "title": "Storage Container",
    "icon": "S3",
    "schema": {
      "properties": {
        "publicAccess": {
          "title": "Public Access",
          "type": "string"
        },
        "hasImmutabilityPolicy": {
          "title": "Has Immutability Policy",
          "type": "boolean"
        },
        "hasLegalHold": {
          "title": "Has Legal Hold",
          "type": "boolean"
        },
        "deleted": {
          "title": "Deleted",
          "type": "boolean"
        },
        "deletedTime": {
          "title": "Deleted Time",
          "type": "string"
        },
        "remainingRetentionDays": {
          "title": "Remaining Retention Days",
          "type": "number"
        },
        "leaseStatus": {
          "title": "Lease Status",
          "type": "string"
        },
        "leaseState": {
          "title": "Lease State",
          "type": "string"
        },
        "defaultEncryptionScope": {
          "title": "Default Encryption Scope",
          "type": "string"
        },
        "version": {
          "title": "Version",
          "type": "string"
        }
      },
      "required": []
    },
    "mirrorProperties": {},
    "calculationProperties": {},
    "relations": {
      "storageAccount": {
        "target": "storageAccount",
        "title": "Storage Account",
        "required": false,
        "many": false
      }
    }
  }
```

</details>

<details>
<summary>port-app-config.yaml</summary>

```yaml
  - kind: Microsoft.Storage/storageAccounts/blobServices/containers
    selector:
        query: "true"
        # azure resource api version to query
        apiVersion: '2023-01-01'
    port:
      entity:
        mappings:
          # lower case the resource group namespace and name to align with other azure resources
          identifier: '.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | join("/")'
          title: .name
          blueprint: '"storageContainer"'
          properties:
            publicAccess: .properties.publicAccess
            hasImmutabilityPolicy: .properties.hasImmutabilityPolicy
            hasLegalHold: .properties.hasLegalHold
            deleted: .properties.deleted
            deletedTime: .properties.deletedTime
            remainingRetentionDays: .properties.remainingRetentionDays
            leaseStatus: .properties.leaseStatus
            leaseState: .properties.leaseState
            defaultEncryptionScope: .properties.defaultEncryptionScope
            version: .properties.version
          relations:
            # lower case the resource group namespace and name to align with other azure resources
            storageAccount: '.id | split("/") | .[3] |= ascii_downcase | .[4] |= ascii_downcase | .[:-4] |join("/")'
```

</details>


## Adding a new Azure Resource kind

Adding new azure resource that the integration will know how to handle requires the following steps:

### Blueprints
To add a new Azure Resource kind, you'll need to add a new blueprint to the `blueprints.json` file.

### Mapping
To add a new Azure Resource kind, you'll need to add a new mapping to the `port-app-config.yaml` file.
- The mapping **must** contain an `apiVersion` field under the `selector` section. The `apiVersion` is a required field when querying Azure resources. To find the correct `apiVersion` for the resource you want to query, you can use the [Azure REST API](https://docs.microsoft.com/en-us/rest/api/azure/) documentation to find the resource you want to query.
- The mapping **must** lower case the resource group namespace and name in the identifier as well to any other relation, so it will be able to relate to the resource group blueprint. (Example: `resourceGroups` -> `resourcegroups`) This is due to the fact that each azure API returns the resource group namespace and name in a different format, and we want to align them all to the same format. here is an example on how to apply it: `.id | split("/") | .[3] |= ascii_downcase |.[4] |= ascii_downcase | join("/")`.

### Authorization 
When adding new Azure resource we need to make sure our exporter has permissions to query it.
To do so we will need to add a new action permission to the integration role definition.
- The action permission should be added to the `actions` section of the integration role definition.

### Event Grid
When adding new Azure resource we need to make sure our exporter will be able to receive events related to it.
To do so we will need to add a new event filter to the integration event grid subscription. For more information on [action permissions](https://learn.microsoft.com/en-us/azure/role-based-access-control/role-definitions#actions)

### Example
Here is an example on how to apply it, for more information on the different inputs please refer to our terraform module [documentation](https://registry.terraform.io/modules/port-labs/ocean-containerapp/azure/latest/examples/azure-integration).
and apply the terraform changes.

`Microsoft.Network/virtualNetworks` is the resource we want to add.

Edit the `main.tf` file and add the following:

```hcl
# Copying the following module into a main.tf file
module "my-azure-integration" {
	source = "port-labs/integration-factory/ocean//examples/azure_container_app_azure_integration" 
	version = ">=0.0.15" 
	port_client_id = "<PORT_CLIENT_ID>"
	port_client_secret = "<PORT_CLIENT_SECRET>"
	port_base_url = "https://api.getport.io" 
	initialize_port_resources = true # When set to true the integration will create default blueprints + JQ Mappings
	integration_identifier = "my-azure-integration" # Change the identifier to describe your integration
	event_listener = {
 	 type = "POLLING"
	} 
  	event_grid_event_filter_list = ["Microsoft.Resources/subscriptions/resourceGroups","Microsoft.Network/virtualNetworks","Microsoft.App/containerApp","Microsoft.Storage/storageAccounts","Microsoft.Compute/virtualMachines","Microsoft.Network/loadBalancers"] # A list of resources to filter events from Azure.
	action_permissions_list = ["Microsoft.Resources/subscriptions/resourceGroups/read","microsoft.network/virtualnetworks/read","Microsoft.Resources/subscriptions/resources/read","Microsoft.app/containerapps/read","Microsoft.Storage/storageAccounts/*/read","Microsoft.ContainerService/managedClusters/read","Microsoft.Network/loadBalancers/read"] # A list of permissions that will be assigned to the Azure Integration User to export Azure Resources.
	additional_environment_variables = {
	
	}
	additional_secrets = {
		OCEAN__INTEGRATION__CONFIG__SUBSCRIPTION_ID = "<SUBSCRIPTION_ID>" # Azure subscription ID to export resources from
	}
}
```

```sh
az login
terraform init
terraform apply
```

Let's go over the changes we made:
- We added a new action permission to the integration role definition: `"microsoft.network/virtualnetworks/read"`.
- We added a new event filter to the integration event grid subscription: `"Microsoft.Network/virtualNetworks"` this will check if the operation name received from the event grid contains `"Microsoft.Network/virtualNetworks"`.

Note that currently the terraform module doesn't support just appending to the default lists, to allow overriding the default list, so we need to pass the full list of action permissions and event filters.

The apiVersion we want to query of `Microsoft.Network/virtualNetworks` is `2023-02-01` which we can find in the [Azure REST API](https://learn.microsoft.com/en-us/rest/api/virtualnetwork/virtual-networks/list)


## Runnning Localhost
```sh
make run
```
or
```sh
ocean sail
```

## Running Tests

`make test`

## Access Swagger Documentation

> <http://localhost:8080/docs>

## Access Redoc Documentation

> <http://localhost:8080/redoc>


## Folder Structure
The azure integration suggested folder structure is as follows:

```
azure/
├─ main.py
├─ pyproject.toml
└─ Dockerfile
```