# ECS Cluster Examples

This directory contains examples for AWS ECS Cluster integration with Port.

## Files

- **ecs-cluster-mappings.yaml**: Port app configuration mapping for ECS clusters
- **ecs-cluster-raw-data.json**: Example raw data from AWS ECS API
- **ecs-cluster-expected-output.json**: Expected output after transformation for Port
- **ecs-cluster-blueprint.json**: Example blueprint definition for ECS clusters

## Default Actions

The ECS cluster integration includes the following default actions:

- **GetClusterArnAction**: Extracts the cluster ARN (used as identifier)
- **ECSClusterDetailsAction**: Fetches detailed cluster information including tags, settings, configurations, statistics, and attachments

## Optional Actions

The following optional actions can be included:

- **GetClusterPendingTasksAction**: Fetches up to 100 pending task ARNs for the cluster

## Usage

To use the ECS cluster integration, include the following in your Port app configuration:

```yaml
resources:
  - kind: AWS::ECS::Cluster
    selector:
      query: 'true'
      includeActions:
        - GetClusterPendingTasksAction  # Optional
    port:
      entity:
        mappings:
          identifier: .Properties.clusterArn
          title: .Properties.clusterName
          blueprint: '"ecsCluster"'
          properties:
            clusterName: .Properties.clusterName
            status: .Properties.status
            activeServicesCount: .Properties.activeServicesCount
            pendingTasksCount: .Properties.pendingTasksCount
            runningTasksCount: .Properties.runningTasksCount
            registeredContainerInstancesCount: .Properties.registeredContainerInstancesCount
            capacityProviders: .Properties.capacityProviders
            defaultCapacityProviderStrategy: .Properties.defaultCapacityProviderStrategy
            tags: .Properties.tags
            settings: .Properties.settings
            configurations: .Properties.configurations
            statistics: .Properties.statistics
            attachments: .Properties.attachments
            attachmentsStatus: .Properties.attachmentsStatus
            serviceConnectDefaults: .Properties.serviceConnectDefaults
            pendingTaskArns: .Properties.pendingTaskArns
```

## Properties

The ECS cluster integration provides the following properties:

- **clusterName**: The name of the ECS cluster
- **status**: The status of the ECS cluster (ACTIVE, INACTIVE, PROVISIONING, DEPROVISIONING)
- **activeServicesCount**: The number of active services in the cluster
- **pendingTasksCount**: The number of pending tasks in the cluster
- **runningTasksCount**: The number of running tasks in the cluster
- **registeredContainerInstancesCount**: The number of registered container instances in the cluster
- **capacityProviders**: The capacity providers associated with the cluster
- **defaultCapacityProviderStrategy**: The default capacity provider strategy for the cluster
- **tags**: The tags associated with the cluster
- **settings**: The settings for the cluster (e.g., container insights)
- **configurations**: The configurations for the cluster (e.g., execute command configuration)
- **statistics**: The statistics for the cluster (e.g., CPU and memory utilization)
- **attachments**: The attachments for the cluster (e.g., ENI attachments)
- **attachmentsStatus**: The status of attachments for the cluster
- **serviceConnectDefaults**: The service connect defaults for the cluster
- **pendingTaskArns**: The ARNs of pending tasks in the cluster (when GetClusterPendingTasksAction is included)

**Note**: The cluster ARN is used as the identifier and is not included as a separate property to avoid duplication.
