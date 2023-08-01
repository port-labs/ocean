resource "aws_ssm_parameter" "ocean_gitlab_token_mapping" {
  name  = "ocean_gitlab_token_mapping"
  type  = "SecureString"
  value = jsonencode({
    "glpat-jQNe7NYypFHNcaZo_ybA" = ["getport-labs/**"]
  })
}

module "port_ocean_ecs_lb" {
  source  = "../../../modules/aws/ecs_lb"
  vpc_id  = "vpc-0123456789abcdef0"  # Example VPC ID
  subnets = [
    "subnet-0123456789abcdef0",     # Example Subnet ID 1
    "subnet-abcdef0123456789",      # Example Subnet ID 2
  ]
  certificate_domain_name = "example.com"  # optional, example certificate domain name
}

module "port_ocean_ecs" {
  source = "../../../modules/aws/ecs_service"

  subnets      = module.port_ocean_ecs_lb.subnets
  cluster_name = "my-ecs-cluster"

  lb_targ_group_arn = module.port_ocean_ecs_lb.target_group_arn
  security_groups   = module.port_ocean_ecs_lb.security_groups

  port = {
    client_id     = "8u9vLK45sT3QwY2X"
    client_secret = "3ebF1Wd9g7fAtJKc0r4zM2sR8lnyX5NQ"
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