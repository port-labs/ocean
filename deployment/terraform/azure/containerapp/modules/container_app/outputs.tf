output "container_app_latest_fqdn" {
  value = azurerm_container_app.ocean-container-app.latest_revision_fqdn
}

output "container_app_outbound_ip_addresses" {
  value = azurerm_container_app.ocean-container-app.outbound_ip_addresses
}

output "container_latest_revision_name" {
  value = azurerm_container_app.ocean-container-app.latest_revision_name
}