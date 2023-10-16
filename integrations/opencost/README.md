# opencost

Ocean integration for OpenCost

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

## Deployment to Port

For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration in your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.config.opencostHost: The URL of you OpenCost server. Used to make API calls
# integration.config.window: Duration of time over which to query. Accepts: words like today, week, month, yesterday, lastweek, lastmonth. Durations like 30m, 12h, 7d are also accepted by the API. If none is provided, it defaults to today

helm upgrade --install my-opencost-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
	--set integration.identifier="my-opencost-integration"  \
	--set integration.type="opencost"  \
	--set integration.eventListener.type="POLLING"  \
	--set integration.config.opencostHost="https://example.com"
```
## Supported Kinds

### Cost

The mapping should refer to one of the cost objects from the example response: [OpenCost Swagger documentation](https://github.com/opencost/opencost/blob/develop/docs/swagger.json)

<details>
<summary>blueprints.json</summary>

```json
{
    "identifier": "openCostResourceAllocation",
    "description": "This blueprint represents an OpenCost resource allocation in our software catalog",
    "title": "OpenCost Resource Allocation",
    "icon": "OpenCost",
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
  - kind: cost
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          blueprint: '"openCostResourceAllocation"'
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
              ramBytes: .ramBytes
              ramCost: .ramCost
              ramEfficiency: .ramEfficiency
              sharedCost: .sharedCost
              externalCost: .externalCost
              totalCost: .totalCost
              totalEfficiency: .totalEfficiency
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
The opencost integration suggested folder structure is as follows:

```
opencost/
├─ main.py
├─ pyproject.toml
└─ Dockerfile
```