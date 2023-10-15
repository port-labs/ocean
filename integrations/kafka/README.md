# Kafka

Ocean Integration to import information from a Kafka cluster into Port. 

The integration supports importing metadata regarding the Kafka cluster, brokers and topics.

## Deployment

For more information about the installation visit the [Port Ocean helm chart](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean)

```bash
# The following script will install an Ocean integration in your K8s cluster using helm
# integration.identifier: Change the identifier to describe your integration
# integration.secrets.clusterConfMapping: Mapping of Kafka cluster names to Kafka client config. example: {\"my cluster\":{\"bootstrap.servers\": \"localhost:9092\"}}

helm upgrade --install my-kafka-integration port-labs/port-ocean \
	--set port.clientId="CLIENT_ID"  \
	--set port.clientSecret="CLIENT_SECRET"  \
	--set initializePortResources=true  \
    --set scheduledResyncInterval=60  \
	--set integration.identifier="my-kafka-integration"  \
	--set integration.type="kafka"  \
	--set integration.eventListener.type="POLLING"  \
	--set integration.secrets.clusterConfMapping="{\"local\":{\"bootstrap.servers\": \"localhost:9092\"}}"
```

## Supported Kinds

### Cluster

The mapping should refer to a cluster from the following example response:

```json
{
  "name": "local",
  "controller_id": "1"
}
```

<details>
<summary>blueprints.json</summary>

```json
{
  "identifier": "cluster",
  "title": "Cluster",
  "icon": "Kafka",
  "schema": {
    "properties": {
      "controllerId": {
        "title": "Controller ID",
        "type": "string"
      }
    }
  }
}
```

</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
createMissingRelatedEntities: false
deleteDependentEntities: true
resources:
  - kind: cluster
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .name
          title: .name
          blueprint: '"cluster"'
          properties:
            controllerId: .controller_id
```

</details>

### Broker

The mapping should refer to a broker from the following example response:

```json
{
    "id": "1",
    "address": "localhost:9092/1",
    "cluster_name": "local",
    "config": {"key": "value", ...}
}
```

<details>
<summary>blueprints.json</summary>

```json
{
  "identifier": "broker",
  "title": "Broker",
  "icon": "Kafka",
  "schema": {
    "properties": {
      "address": {
        "title": "Address",
        "type": "string"
      },
      "region": {
        "title": "Region",
        "type": "string"
      },
      "version": {
        "title": "Version",
        "type": "string"
      },
      "config": {
        "title": "Config",
        "type": "object"
      }
    }
  },
  "relations": {
    "cluster": {
      "target": "cluster",
      "required": true,
      "many": false
    }
  }
}
```

</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
createMissingRelatedEntities: false
deleteDependentEntities: true
resources:
  - kind: broker
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .cluster_name + "_" + (.id | tostring)
          title: .cluster_name + " " + (.id | tostring)
          blueprint: '"broker"'
          properties:
            address: .address
            region: .config."broker.rack"
            version: .config."inter.broker.protocol.version"
            config: .config
          relations:
            cluster: .cluster_name
```

</details>

### Topic

The mapping should refer to a topic from the following example response:

```json
{
    "name": "_consumer_offsets",
    "cluster_name": "local",
    "partitions": [
      {
        "id": 0,
        "leader": 2,
        "replicas": [2, 1, 3],
        "isrs": [3, 2, 1]
      }
    ],
    "config": {"key": "value", ...}
}
```

<details>
<summary>blueprints.json</summary>

```json
{
  "identifier": "topic",
  "title": "Topic",
  "icon": "Kafka",
  "schema": {
    "properties": {
      "replicas": {
        "title": "Replicas",
        "type": "number"
      },
      "partitions": {
        "title": "Partitions",
        "type": "number"
      },
      "compaction": {
        "title": "Compaction",
        "type": "boolean"
      },
      "retention": {
        "title": "Retention",
        "type": "boolean"
      },
      "deleteRetentionTime": {
        "title": "Delete Retention Time",
        "type": "number"
      },
      "partitionsMetadata": {
        "title": "Partitions Metadata",
        "type": "array"
      },
      "config": {
        "title": "Config",
        "type": "object"
      }
    }
  },
  "relations": {
    "cluster": {
      "target": "cluster",
      "required": true,
      "many": false
    },
    "brokers": {
      "target": "broker",
      "required": false,
      "many": true
    }
  }
}
```

</details>
<details>
  <summary>port-app-config.yaml</summary>

```yaml
createMissingRelatedEntities: false
deleteDependentEntities: true
resources:
  - kind: topic
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .cluster_name + "_" + .name
          title: .cluster_name + " " + .name
          blueprint: '"topic"'
          properties:
            replicas: .partitions[0].replicas | length
            partitions: .partitions | length
            compaction: .config."cleanup.policy" | contains("compact")
            retention: .config."cleanup.policy" | contains("delete")
            deleteRetentionTime: .config."delete.retention.ms"
            partitionsMetadata: .partitions
            config: .config
          relations:
            cluster: .cluster_name
            brokers: '[.cluster_name + "_" + (.partitions[].replicas[] | tostring)] | unique'
```

</details>


## Development

### Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

### Installation

```sh
make install
```

### Runnning Localhost

```sh
make run
```

or

```sh
ocean sail
```

### Running Tests

`make test`

### Access Swagger Documentation

> <http://localhost:8080/docs>

### Access Redoc Documentation

> <http://localhost:8080/redoc>

### Folder Structure
The kafka integration suggested folder structure is as follows:

```
kafka/
├─ main.py
├─ pyproject.toml
└─ Dockerfile
```