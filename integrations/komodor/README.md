# Komodor

An integration used to import Komodor resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/)
## Install

## Use
- The integration works best when installed alongside port k8s exporter. If you've opted to use it, in order to configure relations between komodor service and k8s workload add the following to the mapping and blueprint:


**Mapping**
```yaml title="mapping"
  - kind: komodorService
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .kind + "-" + .cluster + "-" + .namespace + "-" + .service
          blueprint: '"komodorService"'
          properties: {}
          relations:
            Workload: .service + "-" + .kind + "-" + .namespace + "-" + .cluster
```

**Blueprint (only modify the relations key)**
```json title="blueprint"
{
  "identifier": "komodorService",
  "title": "komodorService",
  "icon": "Komodor",
  "schema": {
    "properties": "DON'T CHANGE",
    "required": []
  },
  "mirrorProperties": {},
  "calculationProperties": {},
  "aggregationProperties": {},
  "relations": {
    "Workload": {
      "title": "Workload",
      "target": "workload",
      "required": false,
      "many": false
    }
  }
}
```

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)
