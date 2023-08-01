resource "aws_ssm_parameter" "ocean_gitlab_token_mapping" {
  name  = "ocean_gitlab_token_mapping"
  type  = "SecureString"
  value = jsonencode(var.token_mapping)
}

module "port_ocean_ecs_lb" {
  source                  = "../../../aws/ecs_lb"
  vpc_id                  = var.vpc_id
  subnets                 = var.subnets
  certificate_domain_name = var.certificate_domain_name
}

module "port_ocean_ecs" {
  source = "../../../aws/ecs_service"

  subnets      = module.port_ocean_ecs_lb.subnets
  cluster_name = var.cluster_name

  lb_targ_group_arn = module.port_ocean_ecs_lb.target_group_arn
  security_groups   = module.port_ocean_ecs_lb.security_groups

  integration_version = var.integration_version
  port                = var.port

  event_listener = var.event_listener

  integration = {
    type       = "gitlab"
    identifier = var.integration_identifier
    config     = {
      app_host = module.port_ocean_ecs_lb.dns_name
    }
  }

  additional_secrets = [
    {
      name      = "OCEAN__INTEGRATION__CONFIG__TOKEN_MAPPING"
      valueFrom = aws_ssm_parameter.ocean_gitlab_token_mapping.name
    }
  ]

  additional_policy_statements = [
    {
      actions   = ["ssm:GetParameters"]
      resources = [aws_ssm_parameter.ocean_gitlab_token_mapping.arn]
    }
  ]
}