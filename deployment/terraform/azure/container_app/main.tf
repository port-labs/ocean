locals {
  prefix = "port-ocean"
}

resource "azurerm_resource_group" "ocean-rg" {
  count   = var.resource_group_name != null ? 0 : 1
  name     = "${local.prefix}-${var.integration.type}-${var.integration.identifier}-rg"
  location = var.location
}

module "port_ocean_authorization" {
  source = "../modules/authorization"
  location = var.location
  resource_group_name = var.resource_group_name != null ? var.resource_group_name : azurerm_resource_group.ocean-rg[0].name
  integration = var.integration
  permissions = var.permissions
  subscription_id = var.subscription_id
}

module "port_ocean_container_app" {
  source= "./modules/container_app"
  integration = var.integration
  port = var.port
  initialize_port_resources = var.initialize_port_resources
  location = var.location
  resource_group_name = var.resource_group_name != null ? var.resource_group_name : azurerm_resource_group.ocean-rg[0].name
  container_app_environment_id = var.container_app_environment_id
  log_analytics_workspace_id = var.log_analytics_workspace_id
  image = var.image
  min_replicas = var.min_replicas
  max_replicas = var.max_replicas
  user_assigned_identity_ids = [module.port_ocean_authorization.user_assigned_identity_id]
  user_assigned_client_id = module.port_ocean_authorization.user_assigned_identity_client_id
  additional_secrets = var.additional_secrets
  additional_environment_variables = var.additional_environment_variables
}