module "port_ocean_ecs_lb" {
  count                   = var.allow_incoming_requests ? 1 : 0
  source                  = "./modules/ecs_lb"
  vpc_id                  = var.vpc_id
  subnets                 = var.subnets
  certificate_domain_name = var.certificate_domain_name
}

module "port_ocean_ecs" {
  source = "./modules/ecs_service"

  subnets      = var.subnets
  cluster_name = var.cluster_name


  lb_targ_group_arn = var.allow_incoming_requests ? module.port_ocean_ecs_lb[0].target_group_arn : ""
  security_groups   = var.security_groups

  port = {
    client_id     = var.port.client_id
    client_secret = var.port.client_secret
  }

  integration_version       = var.integration_version
  initialize_port_resources = var.initialize_port_resources
  event_listener            = var.event_listener

  integration = {
    type       = var.integration.type
    identifier = var.integration.identifier
    config     = var.allow_incoming_requests ?  merge({
      app_host = module.port_ocean_ecs_lb[0].dns_name
    }, var.integration.config) : var.integration.config
  }

  secrets = var.secrets
}