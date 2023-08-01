resource "aws_ssm_parameter" "ocean_gitlab_token_mapping" {
  name  = "ocean_gitlab_token_mapping"
  type  = "SecureString"
  value = jsonencode({
    "<GITLAB_GROUP_TOKEN>" = ["<GITLAB_PATH_TO_RUN_FOR_TOKEN>"] # e.g "glpat-jQNe7NYypFHNcaZo_ybA" = ["getport-labs/**"]
  })
}

module "port_ocean_ecs_lb" {
  source  = "../../../modules/aws/ecs_lb"
  vpc_id  = "<VPC_ID>"
  subnets = [
    "<SUBNET_ID_1>",
    "<SUBNET_ID_2>",
    "<SUBNET_ID_3>"
  ]
  certificate_domain_name = "<CERTIFICATE_DOMAIN_NAME>" # optional
}

module "port_ocean_ecs" {
  source = "../../../modules/aws/ecs_service"

  subnets      = module.port_ocean_ecs_lb.subnets
  cluster_name = "<ECS_CLUSTEr_NAME>"

  lb_targ_group_arn = module.port_ocean_ecs_lb.target_group_arn
  security_groups   = module.port_ocean_ecs_lb.security_groups

  port = {
    client_id     = "<CLIENT_ID>"
    client_secret = "<CLIENT_SECRET>"
  }

  initialize_port_resources = true
  event_listener            = {
    type = "POLLING"
  }

  integration = {
    type       = "gitlab"
    identifier = "my-gitlab-integration"
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