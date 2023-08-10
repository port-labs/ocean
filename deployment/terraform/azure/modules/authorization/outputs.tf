output "user_assigned_identity_id" {
  value = azurerm_user_assigned_identity.ocean-azure-assigned-identity.id
}

output "user_assigned_identity_client_id" {
  value = azurerm_user_assigned_identity.ocean-azure-assigned-identity.client_id
}

output "subscription_id" {
  value = local.subscription_id
}