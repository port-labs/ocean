locals {
  prefix = "port-ocean"
  env = [
    {
      name  = upper("OCEAN__INITIALIZE_PORT_RESOURCES"),
      value = var.initialize_port_resources ? "true" : "false"
    },
    {
      name  = upper("OCEAN__EVENT_LISTENER")
      value = jsonencode({
        for key, value in var.event_listener : key => value if value != null
      })
    },
    {
      name  = upper("OCEAN__INTEGRATION")
      value = jsonencode(var.integration)
    }
  ]
  port_credentials_secret_name = "ocean-port-credentials"
}

resource "azurerm_log_analytics_workspace" "ocean-log-analytics" {
  count   = var.log_analytics_workspace_id != null ? 0 : 1
  name                = "${local.prefix}-${var.integration.type}-${var.integration.identifier}-law"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "ocean-container-app-env" {
  count                  = var.container_app_environment_id != null ? 0 : 1
  name                   = "${local.prefix}-${var.integration.type}-${var.integration.identifier}-env"
  location               = var.location
  resource_group_name    = var.resource_group_name
  log_analytics_workspace_id = var.log_analytics_workspace_id != null ? var.log_analytics_workspace_id : azurerm_log_analytics_workspace.ocean-log-analytics[0].id
}


resource "azurerm_container_app" "ocean-container-app" {
  name = "${local.prefix}-${var.integration.type}-${var.integration.identifier}"
  container_app_environment_id = var.container_app_environment_id != null ? var.container_app_environment_id : azurerm_container_app_environment.ocean-container-app-env[0].id
  resource_group_name = var.resource_group_name
  revision_mode = "Single"
  identity {
    type = "UserAssigned"
    identity_ids = var.user_assigned_identity_ids
  }
  ingress {
    external_enabled = var.assign_public_ip
    target_port = var.container_port
    traffic_weight {
      percentage = 100
      latest_revision = true
    }
  }
  template {
    min_replicas = 1
    max_replicas = 1
    container {
      name = "${local.prefix}-${var.integration.type}"
      cpu = var.cpu
      memory = var.memory
      image = var.image != null ? var.image : "${var.image_registry}/port-ocean-${var.integration.type}:${var.integration_version}"
      dynamic "env" {
        for_each = local.env
        content {
          name  = env.value.name
          value = env.value.value
        }
      }
      dynamic "env" {
        for_each = var.additional_environment_variables
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "AZURE_CLIENT_ID"
        value = var.user_assigned_client_id
      }
      env {
        name = "OCEAN__PORT"
        secret_name = local.port_credentials_secret_name
      }
      dynamic "env" {
        for_each = var.additional_secrets
        content {
          name        = env.key
          secret_name = replace("ocean-${lower(env.key)}", "_", "-")
        }
      }
    }
  }
  secret {
    name = local.port_credentials_secret_name
    value = jsonencode({
      for key, value in var.port : key => value if value != null
    })
  }
  dynamic "secret" {
    for_each = var.additional_secrets
    content {
      name = replace("ocean-${lower(secret.key)}", "_", "-")
      value = secret.value
    }
  }
}

