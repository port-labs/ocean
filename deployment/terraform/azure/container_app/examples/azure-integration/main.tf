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

module "ocean_integration" {
  source       = "../.."

  # required port parameters so that the integration could communicate with Port
  port = {
    client_id     = var.port_client_id
    client_secret = var.port_client_secret
    base_url = var.port_base_url
  }

  initialize_port_resources = true

  # required port integration parameters so Port could identify the integration
  integration = {
    type       = "azure"
    identifier = "az1"
    config     = {
    }
  }
  # optional port integration parameters
  subscription_id = "/subscriptions/xxxxxx"
  location = "East US 2"

  image = "ghcr.io/port-labs/port-ocean-azure:v0.1.0rc11"

  permissions = {
    actions = [
      "microsoft.app/containerapps/read",
      "Microsoft.Storage/storageAccounts/read",
      "Microsoft.ContainerService/managedClusters/read",
      "Microsoft.Network/loadBalancers/read",
      "Microsoft.Resources/subscriptions/resourceGroups/read",
      "Microsoft.Resources/subscriptions/resources/read",
    ]
    not_actions = []
    data_actions = []
    not_data_actions = []
  }

  additional_secrets = {
      OCEAN__INTEGRATION__CONFIG__SUBSCRIPTION_ID = "xxxxxxxxx"
  }
  additional_environment_variables = {
    OCEAN__INTEGRATION__CONFIG__SOME_ENV_VAR = "some-value"
  }
}

resource "azurerm_eventgrid_system_topic" "subscription_event_grid_topic" {
  name                = "subscription-event-grid-topic"
  resource_group_name = module.ocean_integration.resource_group_name
  location            = "Global"
  topic_type = "Microsoft.Resources.Subscriptions"
  source_arm_resource_id = module.ocean_integration.subscription_id
}


resource "azurerm_eventgrid_system_topic_event_subscription" "subscription_event_grid_topic_subscription" {
  name                = replace(replace("ocean-${module.ocean_integration.integration.type}-${module.ocean_integration.integration.identifier}-subscription","_", "-"),".","-")
  resource_group_name = azurerm_eventgrid_system_topic.subscription_event_grid_topic.resource_group_name
  system_topic   = azurerm_eventgrid_system_topic.subscription_event_grid_topic.name

  included_event_types = [
    "Microsoft.Resources.ResourceWriteSuccess",
    "Microsoft.Resources.ResourceWriteFailure",
    "Microsoft.Resources.ResourceDeleteSuccess",
    "Microsoft.Resources.ResourceDeleteFailure",
  ]
  event_delivery_schema = "CloudEventSchemaV1_0"
  webhook_endpoint {
        url = "https://${module.ocean_integration.container_app_latest_fqdn}/integration/events"
    }
  advanced_filtering_on_arrays_enabled = true
  advanced_filter {
    string_contains {
      key    = "data.operationName"
      values = [
        "microsoft.app/containerapps",
        "Microsoft.Storage/storageAccounts",
        "Microsoft.ContainerService/managedClusters",
        "Microsoft.Network/loadBalancers",
        "Microsoft.Compute/virtualMachine",
        "Microsoft.Resources/subscriptions/resourceGroups",
      ]
    }
  }
  delivery_property {
    header_name = "Access-Control-Request-Method"
    type        = "Static"
    value       = "POST"
  }
  delivery_property {
    header_name = "Origin"
    type        = "Static"
    value       = "azure"
  }
}
