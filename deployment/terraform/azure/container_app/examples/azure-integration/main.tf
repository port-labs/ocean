locals {
  # splits the list into chunks of 25 elements, due to the limit of 25 elements in the advanced filtering for each subscription filter
  # https://learn.microsoft.com/en-us/azure/event-grid/event-filtering#limitations
  chunked_resources_filter_values = chunklist(var.resources_filter_values, 25)
  # creates a dictionary with the index of the chunk as key and the chunk as value
  chunked_resouces_filter_dict = { for i in range(length(local.chunked_resources_filter_values)) : i => local.chunked_resources_filter_values[i] }
}

module "ocean_integration" {
  source       = "../.."

  # required port parameters so that the integration could communicate with Port
  port = {
    client_id     = var.port_client_id
    client_secret = var.port_client_secret
    base_url = var.port_base_url
  }

  initialize_port_resources = var.initialize_port_resources

  # required port integration parameters so Port could identify the integration
  integration = {
    type       = "azure"
    identifier = var.integration_identifier
    config     = {
    }
  }
  # optional port integration parameters
  subscription_id = "/subscriptions/${var.subscription_id}"
  location = var.location

  image = var.image

  permissions = {
    actions = var.action_permissions_list
    not_actions = []
    data_actions = []
    not_data_actions = []
  }

  additional_secrets = {
      OCEAN__INTEGRATION__CONFIG__SUBSCRIPTION_ID = var.subscription_id
  }
}

resource "azurerm_eventgrid_system_topic" "subscription_event_grid_topic" {
  # if the event grid topic name is not provided, the module will create a new one
  count               = var.event_grid_system_topic_name != "" ? 0 : 1
  name                = "subscription-event-grid-topic"
  resource_group_name = module.ocean_integration.resource_group_name
  location            = "Global"
  topic_type = "Microsoft.Resources.Subscriptions"
  source_arm_resource_id = module.ocean_integration.subscription_id
}


resource "azurerm_eventgrid_system_topic_event_subscription" "subscription_event_grid_topic_subscription" {
  # creates a subscription for each chunk of filter values ( 25 per chunk )
  for_each            = local.chunked_resouces_filter_dict
  name                = replace(replace("ocean-${module.ocean_integration.integration.type}-${module.ocean_integration.integration.identifier}-subscription-${each.key}","_", "-"),".","-")
  resource_group_name = var.event_grid_resource_group != "" ? var.event_grid_resource_group: azurerm_eventgrid_system_topic.subscription_event_grid_topic[0].resource_group_name
  system_topic        = var.event_grid_system_topic_name != "" ? var.event_grid_system_topic_name : azurerm_eventgrid_system_topic.subscription_event_grid_topic[0].name

  included_event_types = var.included_event_types
  event_delivery_schema = "CloudEventSchemaV1_0"
  webhook_endpoint {
        url = "https://${module.ocean_integration.container_app_latest_fqdn}/integration/events"
    }
  advanced_filtering_on_arrays_enabled = true
  advanced_filter {
    string_contains {
      key    = "data.operationName"
      values = each.value
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
