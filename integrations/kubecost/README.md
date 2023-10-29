# Kubecost

Ocean integration for Kubecost

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

## Deployment to Port

For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration in your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.config.kubecostHost: The URL of you Kubecost server. Used to make API calls

helm upgrade --install my-kubecost-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
	--set integration.identifier="my-kubecost-integration"  \
	--set integration.type="kubecost"  \
	--set integration.eventListener.type="POLLING"  \
	--set integration.config.kubecostHost="https://kubecostInstance:9090"
```
## Supported Kinds

### Kubesystem

The mapping should refer to one of the cost objects from the example response: [Kubecost Allocation API Schema](https://docs.kubecost.com/apis/apis-overview/api-allocation#allocation-schema)

<details>
<summary>blueprints.json</summary>

```json
{
        "identifier": "kubecostResourceAllocation",
        "description": "This blueprint represents an Kubecost resource allocation in our software catalog",
        "title": "Kubecost Resource Allocation",
        "icon": "Cluster",
        "schema": {
          "properties": {
            "cluster": {
              "type": "string",
              "title": "Cluster"
            },
            "namespace": {
              "type": "string",
              "title": "Namespace"
            },
            "startDate": {
              "title": "Start Date",
              "type": "string",
              "format": "date-time"
            },
            "endDate": {
              "title": "End Date",
              "type": "string",
              "format": "date-time"
            },
            "cpuCoreHours": {
              "title": "CPU Core Hours",
              "type": "number"
            },
            "cpuCost": {
              "title": "CPU Cost",
              "type": "number"
            },
            "cpuEfficiency": {
              "title": "CPU Efficiency",
              "type": "number"
            },
            "gpuHours": {
              "title": "GPU Hours",
              "type": "number"
            },
            "gpuCost": {
              "title": "GPU Cost",
              "type": "number"
            },
            "networkCost": {
              "title": "Network Cost",
              "type": "number"
            },
            "loadBalancerCost": {
              "title": "Load Balancer Cost",
              "type": "number"
            },
            "pvCost": {
              "title": "PV Cost",
              "type": "number"
            },
            "pvBytes": {
                "title": "PV Bytes",
                "type": "number"
              },
            "ramBytes": {
              "title": "RAM Bytes",
              "type": "number"
            },
            "ramCost": {
              "title": "RAM Cost",
              "type": "number"
            },
            "ramEfficiency": {
              "title": "RAM Efficiency",
              "type": "number"
            },
            "sharedCost": {
              "title": "Shared Cost",
              "type": "number"
            },
            "externalCost": {
              "title": "External Cost",
              "type": "number"
            },
            "totalCost": {
              "title": "Total Cost",
              "type": "number"
            },
            "totalEfficiency": {
              "title": "Total Efficiency",
              "type": "number"
            }
          },
          "required": []
        },
        "mirrorProperties": {},
        "calculationProperties": {},
        "relations": {}
}
```
</details>

<details>
  <summary>port-app-config.yaml</summary>

```yaml
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
  - kind: kubesystem
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          blueprint: '"kubecostResourceAllocation"'
          identifier: .name
          title: .name
          properties:
              cluster: .properties.cluster
              namespace: .properties.namespace
              startDate: .start
              endDate: .end
              cpuCoreHours: .cpuCoreHours
              cpuCost: .cpuCost
              cpuEfficiency: .cpuEfficiency
              gpuHours: .gpuHours
              gpuCost: .gpuCost
              networkCost: .networkCost
              loadBalancerCost: .loadBalancerCost
              pvCost: .pvCost
              pvBytes: .pvBytes
              ramBytes: .ramBytes
              ramCost: .ramCost
              ramEfficiency: .ramEfficiency
              sharedCost: .sharedCost
              externalCost: .externalCost
              totalCost: .totalCost
              totalEfficiency: .totalEfficiency
```
</details>

### Cloud

The mapping should refer to one of the cost objects from the example response: [Kubecost Cloud Allocation Aggregate API](https://docs.kubecost.com/apis/apis-overview/cloud-cost-api#cloud-cost-aggregate-api)

<details>
<summary>blueprints.json</summary>

```json
 {
        "identifier": "kubecostCloudAllocation",
        "description": "This blueprint represents an Kubecost cloud resource allocation in our software catalog",
        "title": "Kubecost Cloud Allocation",
        "icon": "Cluster",
        "schema": {
          "properties": {
            "provider": {
              "type": "string",
              "title": "Provider"
            },
            "accountID": {
              "type": "string",
              "title": "Account ID"
            },
            "invoiceEntityID": {
              "type": "string",
              "title": "Invoice Entity ID"
            },
            "startDate": {
              "title": "Start Date",
              "type": "string",
              "format": "date-time"
            },
            "endDate": {
              "title": "End Date",
              "type": "string",
              "format": "date-time"
            },
            "listCost": {
              "title": "List Cost Value",
              "type": "number"
            },
            "listCostPercent": {
              "title": "List Cost Percent",
              "type": "number"
            },
            "netCost": {
              "title": "Net Cost Value",
              "type": "number"
            },
            "netCostPercent": {
              "title": "Net Cost Percent",
              "type": "number"
            },
            "amortizedNetCost": {
              "title": "Amortized Net Cost",
              "type": "number"
            },
            "amortizedNetCostPercent": {
              "title": "Amortized Net Cost Percent",
              "type": "number"
            },
            "invoicedCost": {
              "title": "Invoice Cost",
              "type": "number"
            },
            "invoicedCostPercent": {
              "title": "Invoice Cost Percent",
              "type": "number"
            }
          },
          "required": []
        },
        "mirrorProperties": {},
        "calculationProperties": {},
        "relations": {}
}
```
</details>

<details>
  <summary>port-app-config.yaml</summary>

```yaml
createMissingRelatedEntities: true
deleteDependentEntities: true
resources:
  - kind: cloud
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          blueprint: '"kubecostCloudAllocation"'
          identifier: .properties.service
          title: .properties.service
          properties:
              provider: .properties.provider
              accountID: .properties.accountID
              invoiceEntityID: .properties.invoiceEntityID
              startDate: .window.start
              endDate: .window.end
              listCost: .listCost.cost
              listCostPercent: .listCost.kubernetesPercent
              netCost: .netCost.cost
              netCostPercent: .netCost.kubernetesPercent
              amortizedNetCost: .amortizedNetCost.cost
              amortizedNetCostPercent: .amortizedNetCost.kubernetesPercent
              invoicedCost: .invoicedCost.cost
              invoicedCostPercent: .invoicedCost.kubernetesPercent
```
</details>

## Installation

```sh
make install
```

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
The Kubecost integration suggested folder structure is as follows:

```
kubecost/
├─ main.py
├─ pyproject.toml
└─ Dockerfile
```