variable "port_client_id" {
  type = string
}
variable "port_client_secret" {
  type = string
}
variable "port_base_url" {
  type = string
  default = ""
}
variable "event_grid_topic_name" {
  type = string
  default = ""
  description = "If the event grid topic name is not provided, the module will create a new one"
}
variable "event_grid_resource_group" {
  type = string
  default = ""
    description = "If the event grid resource group is not provided, the module will use the resource group of the event grid topic for the subscription event grid topic"
}
variable "resources_filter_values" {
  type = list(string)
  default = [
        "microsoft.app/containerapps",
        "Microsoft.Storage/storageAccounts",
        "Microsoft.ContainerService/managedClusters",
        "Microsoft.Network/loadBalancers",
        "Microsoft.Compute/virtualMachine",
        "Microsoft.Resources/subscriptions/resourceGroups",
  ]
  description = "The list of resources that will be used for the advanced filtering of the subscription event grid topic"
}
variable "include_event_types" {
  type = list(string)
  default = [
    "Microsoft.Resources.ResourceWriteSuccess",
    "Microsoft.Resources.ResourceWriteFailure",
    "Microsoft.Resources.ResourceDeleteSuccess",
    "Microsoft.Resources.ResourceDeleteFailure",
  ]
  description = "The list of event types to be included in the subscription event grid topic, for more information see https://learn.microsoft.com/en-us/azure/event-grid/event-schema-subscriptions?tabs=event-grid-event-schema#available-event-types"
}

variable "action_permissions_list" {
  type = list(string)
  default = [
      "microsoft.app/containerapps/read",
      "Microsoft.Storage/storageAccounts/read",
      "Microsoft.ContainerService/managedClusters/read",
      "Microsoft.Network/loadBalancers/read",
      "Microsoft.Resources/subscriptions/resourceGroups/read",
      "Microsoft.Resources/subscriptions/resources/read",
  ]
  description = "The list of permissions that will be granted to the integration user"
}

variable "image" {
  type = string
  default = ""
  description = "The image that the integration will use, if not provided the module will use the latest image"
}

variable "initialize_port_resources" {
    type = bool
    default = true
    description = "If true, the module will initialize the port resources"
}

variable "integration_identifier" {
    type = string
    default = "az"
    description = "The identifier of the integration"
}

variable "subscription_id" {
  type    = string
  default = null
  description = "The scope of the integration (e.g (00000000-0000-0000-0000-000000000000)"
}

variable "location" {
  type    = string
  default = "East US 2"
  description = "The location to deploy the container to"
}
