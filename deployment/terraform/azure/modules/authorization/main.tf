data "azurerm_subscription" "current_subscription" {}

locals {
  prefix = "port-ocean"
  subscription_id = var.subscription_id != null ? var.subscription_id : data.azurerm_subscription.current_subscription.id
}

resource "azurerm_role_definition" "ocean-azure-role-definition" {
  name = "${local.prefix}-${var.integration.type}-${var.integration.identifier}-rd"
  scope = local.subscription_id
  description = "This role is used by ${var.integration.type}-${var.integration.identifier} Port Ocean integration"
  permissions {
    actions = var.permissions.actions
    not_actions = var.permissions.not_actions
    data_actions = var.permissions.data_actions
    not_data_actions = var.permissions.not_data_actions
  }
  assignable_scopes = var.permissions_scope != null ? var.permissions_scope : [local.subscription_id]
}

resource "azurerm_user_assigned_identity" "ocean-azure-assigned-identity" {
  name                = "${local.prefix}-${var.integration.type}-${var.integration.identifier}-identity"
  location            = var.location
  resource_group_name = var.resource_group_name
}

resource "azurerm_role_assignment" "ocean-azure-role-assignment" {
  scope = data.azurerm_subscription.current_subscription.id
  role_definition_id = azurerm_role_definition.ocean-azure-role-definition.role_definition_resource_id
  principal_id = azurerm_user_assigned_identity.ocean-azure-assigned-identity.principal_id
}
