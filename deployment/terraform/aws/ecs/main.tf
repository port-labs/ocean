locals {
  security_groups = concat(
    var.additional_security_groups,
    var.allow_incoming_requests ? module.port_ocean_ecs_lb[0].security_groups : []
  )
  tags = var.tags
}

data "jsonschema_validator" "event_listener_validation" {
  document = jsonencode(var.event_listener)
  schema   = "${path.module}/defaults/event_listener.json"
}

module "port_ocean_ecs_lb" {
  count                      = var.allow_incoming_requests ? 1 : 0
  source                     = "./modules/ecs_lb"
  vpc_id                     = var.vpc_id
  subnets                    = var.subnets
  create_egress_default_sg   = var.create_egress_default_sg
  certificate_domain_name    = var.certificate_domain_name
  create_default_sg          = var.create_default_sg
  is_internal                = var.is_internal
  additional_security_groups = local.security_groups
  tags                       = local.tags
}

module "port_ocean_ecs" {
  source = "./modules/ecs_service"

  subnets          = var.subnets
  cluster_name     = var.cluster_name
  assign_public_ip = var.assign_public_ip

  lb_targ_group_arn          = var.allow_incoming_requests ? module.port_ocean_ecs_lb[0].target_group_arn : ""
  additional_security_groups = local.security_groups
  container_port             = var.container_port
  image_registry             = var.image_registry

  port = {
    client_id     = var.port.client_id
    client_secret = var.port.client_secret
  }

  integration_version       = var.integration_version
  initialize_port_resources = var.initialize_port_resources
  scheduled_resync_interval = var.scheduled_resync_interval
  event_listener            = var.event_listener

  integration = {
    type       = var.integration.type
    identifier = var.integration.identifier
    config = var.allow_incoming_requests ? merge({
      app_host = module.port_ocean_ecs_lb[0].dns_name
    }, var.integration.config) : var.integration.config
  }

  additional_secrets = var.additional_secrets
  tags               = local.tags
}
