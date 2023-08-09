output "container_app_latest_fqdn" {
  value = module.port_ocean_container_app.container_app_latest_fqdn
}

output "container_app_outbound_ip_addresses" {
  value = module.port_ocean_container_app.container_app_outbound_ip_addresses
}

output "container_latest_revision_name" {
  value = module.port_ocean_container_app.container_latest_revision_name
}

output "resource_group_name" {
  value = var.resource_group_name != null ? var.resource_group_name : azurerm_resource_group.ocean-rg[0].name
}

output "location" {
  value = var.location
}

output "subscription_id" {
  value = module.port_ocean_authorization.subscription_id
}

output "integration" {
  value = var.integration
}
